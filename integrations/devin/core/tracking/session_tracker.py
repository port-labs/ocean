"""Completes Port runs that are waiting on Devin session turns.

Devin has no outbound webhooks and Port has no "list in-progress runs" API, so
the durable record of in-flight work is the tags on the Devin sessions
themselves (see `core/tracking/tags.py` and ADR-0041). Every tick lists the
sessions tagged `port:pending:<installationId>`, posts their new messages to
the waiting run's logs, and completes the run once the turn has ended.

All per-turn state kept here (message cursor, cached run) is an optimisation
that the first tick after a restart rebuilds from the tags alone.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun, WorkflowNodeRunLog
from port_ocean.utils.repeat import repeat_every

from clients.client_factory import create_devin_client
from clients.models import SessionMessage, SessionResponse
from core.catalog import upsert_raw_from_background
from core.sessions import DevinSessions
from core.tracking.run_output import (
    completion_output,
    completion_summary,
    iso_from_epoch,
)
from core.tracking.tags import (
    parse_external_id,
    parse_sent_at,
    pending_tag,
    strip_tracking_tags,
)
from core.tracking.turn_state import (
    TurnOutcome,
    TurnState,
    classify,
    to_epoch_seconds,
    turn_has_ended,
)
from integration import ObjectKind

# `create_session` tags the session before `update_run_started` sets the run's
# external ID, so for a short while the run legitimately can't be found by it.
RUN_LOOKUP_GRACE_SECONDS = 300
TIMED_OUT_STATUS_LABEL = "Timed out"
DEVIN_SOURCE = "devin"


@dataclass
class _TurnProgress:
    run: IntegrationRun | None = None
    cursor: str | None = None
    posted_event_ids: set[str] = field(default_factory=set)
    devin_replied: bool = False
    last_devin_message: str | None = None
    last_devin_message_at: int | None = None
    status_label: str | None = None


class SessionTracker:
    def __init__(
        self,
        sessions: DevinSessions,
        installation_id: str,
        interval_seconds: float,
        max_hours: float,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._sessions = sessions
        self._installation_id = installation_id
        self._pending_tag = pending_tag(installation_id)
        self._interval_seconds = interval_seconds
        self._max_turn_seconds = max_hours * 60 * 60
        self._clock = clock
        self._lock = asyncio.Lock()
        self._turns: dict[str, _TurnProgress] = {}
        self._stopped = False

    async def start(self) -> None:
        logger.info(
            f"SessionTracker started (every {self._interval_seconds}s, "
            f"tag {self._pending_tag})"
        )

        @repeat_every(seconds=self._interval_seconds, raise_exceptions=False)
        async def _tick_forever() -> None:
            if not self._stopped:
                await self.tick()

        await _tick_forever()

    def stop(self) -> None:
        self._stopped = True

    async def tick(self) -> None:
        if self._lock.locked():
            logger.debug("SessionTracker tick skipped: previous tick still running")
            return
        async with self._lock:
            seen: set[str] = set()
            try:
                async for page in self._sessions.list_by_tag(self._pending_tag):
                    for session in page:
                        if external_id := parse_external_id(session.tags):
                            seen.add(external_id)
                        await self._process_safely(session)
            except Exception as error:
                logger.error(f"SessionTracker failed to list pending sessions: {error}")
                return
            for external_id in self._turns.keys() - seen:
                del self._turns[external_id]

    async def _process_safely(self, session: SessionResponse) -> None:
        try:
            await self._process(session)
        except Exception as error:
            logger.exception(
                f"SessionTracker failed to process session {session.session_id}: {error}"
            )

    async def _process(self, session: SessionResponse) -> None:
        external_id = parse_external_id(session.tags)
        sent_at = parse_sent_at(session.tags)
        if external_id is None or sent_at is None:
            logger.warning(
                f"Devin session {session.session_id} has a pending tag but no "
                "valid external-id/sent-at tags; removing its tracking tags"
            )
            await self._release(session, external_id)
            return

        turn = self._turns.setdefault(external_id, _TurnProgress())
        run = await self._resolve_run(external_id, turn)
        if run is None:
            if self._now() - sent_at < RUN_LOOKUP_GRACE_SECONDS:
                return
            logger.warning(
                f"No Port run found for {external_id} (session {session.session_id}); "
                "removing its tracking tags"
            )
            await self._release(session, external_id)
            return
        if not ocean.port_client.is_run_in_progress(run):
            await self._release(session, external_id)
            return

        await self._post_new_messages(session, run, turn, sent_at)

        state = classify(session.status, session.status_detail)
        if turn_has_ended(state, session.updated_at, sent_at, turn.devin_replied):
            await self._complete(session, external_id, turn, state, sent_at)
            return
        if self._now() - sent_at > self._max_turn_seconds:
            await self._time_out(session, external_id, sent_at)
            return
        if (
            state.outcome is TurnOutcome.IN_PROGRESS
            and state.label != turn.status_label
        ):
            await ocean.port_client.post_run_log(
                run,
                f"Devin status: {state.label}",
                status_label=state.label,
                should_raise=False,
            )
            turn.status_label = state.label

    async def _resolve_run(
        self, external_id: str, turn: _TurnProgress
    ) -> IntegrationRun | None:
        if turn.run is None:
            turn.run = await ocean.port_client.find_run_by_external_id(external_id)
        return turn.run

    async def _post_new_messages(
        self,
        session: SessionResponse,
        run: IntegrationRun,
        turn: _TurnProgress,
        sent_at: int,
    ) -> None:
        """Post this turn's new messages; never blocks completion handling."""
        try:
            messages, turn.cursor = await self._sessions.list_messages_after(
                session.session_id, turn.cursor
            )
        except httpx.HTTPError as error:
            logger.warning(
                f"Failed to fetch messages for Devin session {session.session_id}: "
                f"{error}"
            )
            return

        new_messages = sorted(
            (
                message
                for message in messages
                if message.event_id not in turn.posted_event_ids
                and to_epoch_seconds(message.created_at) >= sent_at
            ),
            key=lambda message: message.created_at,
        )
        if not new_messages:
            return
        for message in new_messages:
            turn.posted_event_ids.add(message.event_id)
            if message.source == DEVIN_SOURCE:
                turn.devin_replied = True
                turn.last_devin_message = message.message
                turn.last_devin_message_at = to_epoch_seconds(message.created_at)

        try:
            await ocean.port_client.post_run_logs(
                run, [_format_message(message) for message in new_messages]
            )
        except Exception as error:
            logger.warning(
                f"Failed to post Devin messages to run {run.id} "
                f"(session {session.session_id}): {error}"
            )

    async def _complete(
        self,
        session: SessionResponse,
        external_id: str,
        turn: _TurnProgress,
        state: TurnState,
        sent_at: int,
    ) -> None:
        run = await ocean.port_client.find_run_by_external_id(external_id)
        if run is None or not ocean.port_client.is_run_in_progress(run):
            await self._release(session, external_id)
            return

        ended_at = (
            turn.last_devin_message_at
            if state.requires_reply and turn.last_devin_message_at is not None
            else to_epoch_seconds(session.updated_at)
        )
        output = completion_output(session, sent_at, ended_at, turn.last_devin_message)
        success = state.outcome is TurnOutcome.SUCCEEDED

        await ocean.port_client.post_run_log(
            run,
            f"Devin session ended at {output['endedAt']} "
            f"(status: {session.status}"
            + (f"/{session.status_detail}" if session.status_detail else "")
            + ")",
            level="INFO" if success else "ERROR",
            should_raise=False,
        )
        await self._report(
            run, success, completion_summary(output), state.label, output
        )
        await self._release(session, external_id)
        await upsert_raw_from_background(ObjectKind.SESSION, session.raw())

    async def _time_out(
        self, session: SessionResponse, external_id: str, sent_at: int
    ) -> None:
        run = await ocean.port_client.find_run_by_external_id(external_id)
        if run is not None and ocean.port_client.is_run_in_progress(run):
            ended_at = int(self._now())
            await self._report(
                run,
                False,
                f"Devin session {session.session_id} turn did not finish within "
                f"{self._max_turn_seconds // 3600:.0f}h (started "
                f"{iso_from_epoch(sent_at)}); the session was left running",
                TIMED_OUT_STATUS_LABEL,
                {
                    "sessionId": session.session_id,
                    "url": session.url,
                    "startedAt": iso_from_epoch(sent_at),
                    "endedAt": iso_from_epoch(ended_at),
                    "durationSeconds": ended_at - sent_at,
                },
            )
        await self._release(session, external_id)

    async def _report(
        self,
        run: IntegrationRun,
        success: bool,
        message: str,
        status_label: str,
        output: dict[str, Any],
    ) -> None:
        if isinstance(run, WorkflowNodeRun):
            run.output.update(output)
        await ocean.port_client.report_run_completed(
            run, success, message, status_label=status_label
        )

    async def _release(self, session: SessionResponse, external_id: str | None) -> None:
        """Strip the tracking tags. On failure they stay, and the next tick
        retries: the run is no longer in progress, so nothing is reported twice."""
        await self._sessions.replace_tags(
            session.session_id,
            strip_tracking_tags(session.tags, self._installation_id),
        )
        if external_id is not None:
            self._turns.pop(external_id, None)

    def _now(self) -> float:
        return self._clock()


def _format_message(message: SessionMessage) -> WorkflowNodeRunLog:
    return WorkflowNodeRunLog(
        level="INFO", message=f"[{message.source}] {message.message}"
    )


_session_tracker: SessionTracker | None = None


def create_session_tracker() -> SessionTracker:
    global _session_tracker
    if _session_tracker is not None:
        return _session_tracker

    config: dict[str, Any] = ocean.integration_config
    _session_tracker = SessionTracker(
        sessions=DevinSessions(create_devin_client()),
        installation_id=ocean.config.integration.identifier,
        interval_seconds=float(config.get("session_tracking_interval_seconds") or 30),
        max_hours=float(config.get("session_tracking_max_hours") or 72),
    )
    return _session_tracker
