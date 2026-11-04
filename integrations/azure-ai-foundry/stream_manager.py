"""Live Responses stream → Port workflow run logs (action-time only)."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRunLog

from clients.client_factory import create_foundry_client
from helpers.responses_stream import (
    format_responses_sse_log_message,
    parse_responses_sse_payload,
    response_id_from_sse_event,
    success_for_terminal_sse_event,
)

OnResponseIdCallback = Callable[[str], Awaitable[None] | None]
OnTerminalSseCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class ResponsesStreamManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def track(
        self,
        *,
        stream_key: str,
        invoke_url: str,
        response_body: dict[str, Any],
        run: IntegrationRun,
        params: dict[str, Any] | None = None,
        on_response_id: OnResponseIdCallback | None = None,
        stop_on_terminal_sse: bool = False,
        on_terminal_sse: OnTerminalSseCallback | None = None,
    ) -> bool:
        if stream_key in self._tasks:
            return False
        task = asyncio.create_task(
            self._consume_stream(
                stream_key,
                invoke_url,
                response_body,
                run,
                params=params,
                on_response_id=on_response_id,
                stop_on_terminal_sse=stop_on_terminal_sse,
                on_terminal_sse=on_terminal_sse,
            ),
            name=f"foundry-stream-{stream_key}",
        )
        self._tasks[stream_key] = task
        return True

    async def untrack(self, stream_key: str) -> None:
        task = self._tasks.pop(stream_key, None)
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def untrack_for_run(self, run_id: str) -> None:
        prefix = f"{run_id}:"
        for key in list(self._tasks):
            if key.startswith(prefix):
                await self.untrack(key)

    async def join(self, stream_key: str) -> BaseException | None:
        task = self._tasks.get(stream_key)
        if task is None:
            return None
        with contextlib.suppress(asyncio.CancelledError):
            await task
        return task.exception()

    async def _consume_stream(
        self,
        stream_key: str,
        invoke_url: str,
        response_body: dict[str, Any],
        run: IntegrationRun,
        *,
        params: dict[str, Any] | None = None,
        on_response_id: OnResponseIdCallback | None = None,
        stop_on_terminal_sse: bool = False,
        on_terminal_sse: OnTerminalSseCallback | None = None,
    ) -> None:
        client = create_foundry_client()
        buffer: list[WorkflowNodeRunLog] = []
        response: httpx.Response | None = None
        response_id_reported = False
        try:
            response = await client.open_responses_stream(
                invoke_url, response_body, params=params
            )
            async for line in _iter_sse_lines(response):
                if not line.startswith("data:"):
                    continue
                payload = line.removeprefix("data:").strip()
                if not payload or payload == "[DONE]":
                    continue
                parsed = parse_responses_sse_payload(payload)
                if parsed is None:
                    continue
                if on_response_id is not None and not response_id_reported:
                    response_id = response_id_from_sse_event(parsed)
                    if response_id:
                        response_id_reported = True
                        result = on_response_id(response_id)
                        if asyncio.iscoroutine(result):
                            await result
                event_type = parsed.get("type")
                if (
                    stop_on_terminal_sse
                    and isinstance(event_type, str)
                    and success_for_terminal_sse_event(event_type) is not None
                ):
                    if buffer:
                        await _flush_logs(run, buffer)
                    if on_terminal_sse is not None:
                        result = on_terminal_sse(parsed)
                        if asyncio.iscoroutine(result):
                            await result
                    break
                message = format_responses_sse_log_message(parsed)
                if message is None:
                    continue
                buffer.append(
                    WorkflowNodeRunLog(
                        message=message,
                        level="INFO",
                    )
                )
                if len(buffer) >= 10:
                    await _flush_logs(run, buffer)
            if buffer:
                await _flush_logs(run, buffer)
        except asyncio.CancelledError:
            if buffer:
                await _flush_logs(run, buffer)
            raise
        except Exception as error:
            logger.exception(f"Responses stream failed for {stream_key}: {error}")
            raise
        finally:
            self._tasks.pop(stream_key, None)
            if response is not None:
                await response.aclose()


async def _iter_sse_lines(response: httpx.Response):
    async for chunk in response.aiter_lines():
        if chunk:
            yield chunk


async def _flush_logs(run: IntegrationRun, buffer: list[WorkflowNodeRunLog]) -> None:
    if not buffer:
        return
    logs = list(buffer)
    buffer.clear()
    await ocean.port_client.post_run_logs(run, logs)


_stream_manager: ResponsesStreamManager | None = None


def get_stream_manager() -> ResponsesStreamManager:
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = ResponsesStreamManager()
    return _stream_manager
