from __future__ import annotations

import asyncio
import contextlib

import httpx
from anthropic.types.beta.sessions.beta_managed_agents_session_deleted_event import (
    BetaManagedAgentsSessionDeletedEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_status_terminated_event import (
    BetaManagedAgentsSessionStatusTerminatedEvent,
)
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRunLog

from actions.utils import format_session_event
from clients.client_factory import create_anthropic_client

_TERMINAL_STREAM_TYPES = (
    BetaManagedAgentsSessionStatusTerminatedEvent,
    BetaManagedAgentsSessionDeletedEvent,
)

_INITIAL_RECONNECT_BACKOFF = 1.0
_MAX_RECONNECT_BACKOFF = 60.0

_STREAM_TIMEOUT = httpx.Timeout(connect=30.0, read=None, write=5.0, pool=5.0)


class StreamManager:
    """Manages live SSE streams for active Claude sessions.

    Tracks one :class:`asyncio.Task` per session, accumulates formatted log
    entries in a per-session buffer, and flushes them to Port on a periodic
    timer and whenever the batch-size threshold is hit.

    Call :meth:`track` from :class:`TriggerAgentExecutor` immediately after the
    prompt is sent.  Call :meth:`untrack` from
    :class:`TriggerAgentWebhookProcessor` when a terminal webhook arrives —
    it flushes any remaining buffer and returns the set of event IDs that were
    successfully posted, so the webhook processor can backfill only the events
    the stream missed.
    """

    def __init__(
        self,
        max_concurrent: int,
        flush_interval: float,
        flush_batch_size: int,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._flush_interval = flush_interval
        self._flush_batch_size = flush_batch_size

        self._runs: dict[str, IntegrationRun] = {}
        self._buffers: dict[str, list[WorkflowNodeRunLog]] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._tracked: set[str] = set()

        self._shutdown = asyncio.Event()
        self._flush_task: asyncio.Task[None] | None = None

    async def track(self, session_id: str, run: IntegrationRun) -> bool:
        """Register ``session_id`` for live streaming.

        Returns ``False`` (and logs a warning) when the concurrency cap is
        already reached.  The caller should fall back to the Phase-0
        reconciliation path in that case.
        """
        if len(self._tasks) >= self._max_concurrent:
            logger.warning(
                f"StreamManager at capacity ({self._max_concurrent} concurrent "
                f"streams); session {session_id} will not be streamed live"
            )
            return False

        if session_id in self._tracked:
            old_run = self._runs.get(session_id)
            logger.warning(
                f"StreamManager: session {session_id} already tracked "
                f"(run {old_run!r}); re-registering for run {run.id}"
            )
            old_task = self._tasks.pop(session_id, None)
            if old_task is not None and not old_task.done():
                old_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await old_task
            await self._flush(session_id)

        self._tracked.add(session_id)
        self._runs[session_id] = run
        self._buffers[session_id] = []

        task = asyncio.create_task(
            self._stream_session(session_id),
            name=f"stream-{session_id}",
        )
        task.add_done_callback(lambda _: self._tasks.pop(session_id, None))
        self._tasks[session_id] = task

        logger.info(f"StreamManager: tracking session {session_id} for run {run.id}")
        return True

    async def untrack(self, session_id: str) -> bool:
        """Stop streaming ``session_id``, flush any remaining buffer, and return
        whether the session was being actively tracked.

        Returns ``True`` when the session was registered via :meth:`track` so
        the caller can trust the stream and skip full log reconciliation.
        Returns ``False`` when the session was never tracked (e.g. the stream
        manager was not running, the concurrency cap was reached, or the pod
        restarted), in which case the caller should run a full reconciliation
        pass via :func:`post_interaction_logs`.
        """
        was_tracked = session_id in self._tracked
        self._tracked.discard(session_id)

        task = self._tasks.pop(session_id, None)
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        await self._flush(session_id)

        self._runs.pop(session_id, None)
        self._buffers.pop(session_id, None)

        return was_tracked

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    async def start(self) -> None:
        """Start the background flush loop.  Call once from ``on_start()``."""
        self._flush_task = asyncio.create_task(
            self._flush_loop(), name="stream-manager-flush"
        )
        logger.info(
            f"StreamManager started "
            f"(max_concurrent={self._max_concurrent}, "
            f"flush_interval={self._flush_interval}s, "
            f"flush_batch_size={self._flush_batch_size})"
        )

    async def stop(self) -> None:
        """Graceful shutdown: cancel all stream tasks and flush remaining buffers."""
        self._shutdown.set()

        if self._flush_task is not None and not self._flush_task.done():
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._flush_task

        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        for session_id in list(self._runs.keys()):
            try:
                await self._flush(session_id)
            except Exception as exc:
                logger.warning(
                    f"StreamManager: error flushing session {session_id} during stop: {exc!r}"
                )
            await asyncio.sleep(0)

    async def _stream_session(self, session_id: str) -> None:
        """Open a live SSE stream for ``session_id`` and accumulate log entries.

        Reconnects with exponential backoff on any transport error.  Stops
        when a terminal event is received, when cancelled, or on shutdown.
        """
        backoff = _INITIAL_RECONNECT_BACKOFF
        while not self._shutdown.is_set():
            try:
                client = create_anthropic_client()
                stream = await client.async_client.beta.sessions.events.stream(
                    session_id,
                    timeout=_STREAM_TIMEOUT,
                )
                backoff = _INITIAL_RECONNECT_BACKOFF
                async with stream:
                    async for event in stream:
                        try:
                            log = format_session_event(event)
                        except Exception as exc:
                            logger.debug(
                                f"StreamManager: skipping unparseable event "
                                f"(type={getattr(event, 'type', type(event).__name__)!r}) "
                                f"for session {session_id}: {exc!r}"
                            )
                            log = None

                        if log is not None:
                            buf = self._buffers.get(session_id)
                            if buf is not None:
                                buf.append(log)
                                if len(buf) >= self._flush_batch_size:
                                    await self._flush(session_id)

                        if isinstance(event, _TERMINAL_STREAM_TYPES):
                            logger.info(
                                f"StreamManager: session {session_id} reached "
                                f"terminal state ({event.type!r}), closing stream"
                            )
                            await self._flush(session_id)
                            return

                await self._flush(session_id)
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    await self._flush(session_id)
                    raise

            except asyncio.CancelledError:
                await self._flush(session_id)
                raise
            except Exception as exc:
                if session_id not in self._runs:
                    return
                logger.warning(
                    f"StreamManager: stream for session {session_id} failed "
                    f"({exc!r}), reconnecting in {backoff:.1f}s"
                )
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    await self._flush(session_id)
                    raise
                backoff = min(backoff * 2, _MAX_RECONNECT_BACKOFF)

    async def _flush(self, session_id: str) -> None:
        """Post buffered log entries to Port and clear the buffer."""
        buf = self._buffers.get(session_id)
        if not buf:
            return
        self._buffers[session_id] = []
        run = self._runs.get(session_id)
        if run is not None:
            try:
                await ocean.port_client.post_run_logs(run, buf)
                logger.debug(
                    f"StreamManager: flushed {len(buf)} log(s) "
                    f"for session {session_id} to run {run.id}"
                )
            except Exception as exc:
                logger.warning(
                    f"StreamManager: failed to flush {len(buf)} log(s) "
                    f"for session {session_id}: {exc!r}"
                )

    async def _flush_loop(self) -> None:
        """Periodically flush all active session buffers."""
        while not self._shutdown.is_set():
            try:
                await asyncio.sleep(self._flush_interval)
            except asyncio.CancelledError:
                break
            for session_id in list(self._runs.keys()):
                try:
                    await self._flush(session_id)
                except Exception as exc:
                    logger.warning(
                        f"StreamManager: error flushing session {session_id} in flush loop: {exc!r}"
                    )
                await asyncio.sleep(0)


_manager: StreamManager | None = None


async def reattach_active_sessions(manager: StreamManager) -> None:
    """Re-attach streams for sessions that were tracked before a pod restart.

    Scans all active (``running`` / ``rescheduling``) Anthropic sessions for a
    ``portExternalRunId`` metadata key written by :class:`TriggerAgentExecutor`.
    For each match the corresponding Port run is looked up; if it is still in
    progress and is a :class:`WorkflowNodeRun`, the stream is re-attached.
    Best-effort: individual failures are logged and never block startup.
    """
    logger.info("StreamManager: scanning active sessions for reattachment")
    count = 0
    try:
        client = create_anthropic_client()
        async for batch in client.list_active_sessions(limit=manager.max_concurrent):
            for session in batch:
                external_id = session.metadata.get("portExternalRunId")
                if not external_id:
                    continue
                try:
                    run = await ocean.port_client.find_run_by_external_id(external_id)
                    if (
                        run is not None
                        and ocean.port_client.is_run_in_progress(run)
                        and await manager.track(session.id, run)
                    ):
                        count += 1
                except Exception as exc:
                    logger.warning(
                        f"StreamManager: failed to reattach session {session.id} "
                        f"(external_id={external_id!r}): {exc!r}"
                    )
    except Exception as exc:
        logger.warning(f"StreamManager: session scan for reattachment failed: {exc!r}")
    logger.info(f"StreamManager: reattached {count} session(s)")


def get_stream_manager() -> StreamManager:
    """Return the global :class:`StreamManager`, creating it on first call.

    Configuration is read from ``ocean.integration_config`` once at
    initialisation time.  Call ``await get_stream_manager().start()`` from
    ``on_start()`` to launch the background flush loop.
    """
    global _manager
    if _manager is None:
        config = ocean.integration_config
        _manager = StreamManager(
            max_concurrent=int(config.get("max_concurrent_session_streams", 10)),
            flush_interval=float(config.get("flush_interval_seconds", 5.0)),
            flush_batch_size=int(config.get("flush_batch_size", 25)),
        )
    return _manager
