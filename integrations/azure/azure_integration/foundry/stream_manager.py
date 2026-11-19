"""Live Responses stream → Port workflow run logs (action-time only)."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any, Literal

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun, WorkflowNodeRunLog

from azure_integration.foundry.clients.http.foundry_client import create_foundry_client
from azure_integration.foundry.helpers.responses_stream import (
    TERMINAL_SSE_TYPES,
    ResponsesSseEvent,
    format_responses_sse_log_message,
    parse_responses_sse_payload,
    response_id_from_sse_event,
)

OnResponseIdCallback = Callable[[str], Awaitable[None] | None]
OnTerminalSseCallback = Callable[[ResponsesSseEvent], Awaitable[None] | None]
TrackResult = Literal["started", "duplicate", "capacity"]

# Same default as CMA stream manager; not user-configurable.
_MAX_CONCURRENT_STREAMS = 10
_LOG_FLUSH_BATCH_SIZE = 10


class ResponsesStreamManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def active_count(self) -> int:
        return len(self._tasks)

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
    ) -> TrackResult:
        if stream_key in self._tasks:
            return "duplicate"
        if len(self._tasks) >= _MAX_CONCURRENT_STREAMS:
            # Over cap: caller submits non-SSE invoke and relies on webhooks.
            return "capacity"
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
        return "started"

    async def untrack(self, stream_key: str) -> None:
        task = self._tasks.pop(stream_key, None)
        if task is None or task is asyncio.current_task():
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def untrack_for_run(self, run_id: str) -> None:
        prefix = f"{run_id}:"
        for key in list(self._tasks):
            if key.startswith(prefix):
                await self.untrack(key)

    async def shutdown(self) -> None:
        for key in list(self._tasks):
            await self.untrack(key)

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
        terminal_parsed: ResponsesSseEvent | None = None
        try:
            response = await client.open_responses_stream(
                invoke_url, response_body, params=params
            )
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line.removeprefix("data:").strip()
                if not payload:
                    continue
                if payload == "[DONE]":
                    break
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
                message = format_responses_sse_log_message(parsed)
                if message is not None:
                    buffer.append(WorkflowNodeRunLog(message=message, level="INFO"))
                    if len(buffer) >= _LOG_FLUSH_BATCH_SIZE:
                        await _flush_logs(run, buffer)
                if stop_on_terminal_sse and parsed.type in TERMINAL_SSE_TYPES:
                    terminal_parsed = parsed
                    break
            if buffer:
                await _flush_logs(run, buffer)
            if terminal_parsed is not None and on_terminal_sse is not None:
                result = on_terminal_sse(terminal_parsed)
                if asyncio.iscoroutine(result):
                    await result
            elif ocean.port_client.is_run_in_progress(run):
                if response_id_reported:
                    await _complete_or_leave_after_sse_drop(
                        run,
                        note=(
                            "Responses stream ended without a terminal event; "
                            "completing from Foundry GET if terminal"
                        ),
                    )
                else:
                    with contextlib.suppress(Exception):
                        await ocean.port_client.post_run_log(
                            run,
                            "Responses stream ended without a terminal event",
                            level="ERROR",
                        )
                    with contextlib.suppress(Exception):
                        await ocean.port_client.report_run_completed(
                            run,
                            False,
                            status_label="Invoke failed",
                            should_raise=False,
                        )
        except asyncio.CancelledError:
            if buffer:
                await _flush_logs(run, buffer)
            raise
        except Exception as error:
            logger.exception(f"Responses stream failed for {stream_key}: {error}")
            if not ocean.port_client.is_run_in_progress(run):
                return
            if response_id_reported:
                await _complete_or_leave_after_sse_drop(
                    run,
                    note=(
                        f"Responses stream failed after bind; "
                        f"completing from Foundry GET if terminal: {error}"
                    ),
                )
                return
            with contextlib.suppress(Exception):
                await ocean.port_client.post_run_log(
                    run, f"Responses stream failed: {error}", level="ERROR"
                )
            with contextlib.suppress(Exception):
                await ocean.port_client.report_run_completed(
                    run, False, status_label="Invoke failed", should_raise=False
                )
        finally:
            self._tasks.pop(stream_key, None)
            if response is not None:
                with contextlib.suppress(Exception):
                    await response.aclose()


async def _complete_or_leave_after_sse_drop(run: IntegrationRun, *, note: str) -> None:
    with contextlib.suppress(Exception):
        await ocean.port_client.post_run_log(run, note, level="WARNING")

    from azure_integration.foundry.helpers.invoke_completion import (
        _project_endpoint_from_run,
        complete_invoke_run_for_response,
        response_body_for_catalog,
    )
    from azure_integration.foundry.helpers.webhook_scope import FoundryResponseBody

    response_id: str | None = None
    if isinstance(run, WorkflowNodeRun) and isinstance(run.output, dict):
        rid = run.output.get("responseId")
        if isinstance(rid, str) and rid:
            response_id = rid
    if not response_id:
        return
    endpoint = _project_endpoint_from_run(run)
    if not endpoint:
        return
    try:
        body = await response_body_for_catalog(
            response_id, None, project_endpoint=endpoint
        )
    except Exception:
        return
    if not isinstance(body, dict):
        return
    try:
        override = FoundryResponseBody.model_validate(body).success_override()
    except Exception:
        return
    if override is None:
        return
    await complete_invoke_run_for_response(
        run,
        response_id=response_id,
        response_body=body,
        success=override,
        register_catalog=override,
        source=note,
    )


async def _flush_logs(run: IntegrationRun, buffer: list[WorkflowNodeRunLog]) -> None:
    if not buffer:
        return
    logs = list(buffer)
    buffer.clear()
    if not ocean.port_client.is_run_in_progress(run):
        return
    with contextlib.suppress(Exception):
        await ocean.port_client.post_run_logs(run, logs)


_stream_manager: ResponsesStreamManager | None = None


def get_stream_manager() -> ResponsesStreamManager:
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = ResponsesStreamManager()
    return _stream_manager
