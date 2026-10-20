import time
from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from pydantic import Field

from actions.abstract_action_input import AbstractDevinActionInput
from actions.abstract_executor import AbstractDevinExecutor
from actions.exceptions import DevinApiError, SessionBusyError
from actions.utils import installation_id, merge_config, resolve_user_id
from core.tracking.run_output import started_output
from core.tracking.tags import (
    build_external_id,
    has_pending_tag,
    strip_tracking_tags,
    tracking_tags,
)
from core.tracking.turn_state import TurnOutcome, classify
from integration import ObjectKind

SENDING_STATUS_LABEL = "Sending message"
SESSION_RUNNING_STATUS_LABEL = "Session running"
MESSAGE_SENT_STATUS_LABEL = "Message sent"


class SendMessageInputs(AbstractDevinActionInput):
    sessionId: str = Field(min_length=1)
    message: str = Field(min_length=1)
    messageAsUserEmail: str | None = None
    reportCompletion: bool = True
    config: dict[str, Any] | None = None


class SendMessageExecutor(AbstractDevinExecutor):
    """Executor for the `send_message` action.

    With `reportCompletion`, the tracking tags are appended *before* the message
    is sent, so a turn can never start without the `SessionTracker` being able
    to find it. Runs are serialized per session so two follow-ups can't race.
    """

    ACTION_NAME = "send_message"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return run.execution_properties.get("sessionId")

    async def execute(self, run: IntegrationRun) -> None:
        inputs = SendMessageInputs.from_execution_properties(run.execution_properties)
        session_id = inputs.sessionId

        await ocean.port_client.post_run_log(
            run,
            f"Sending a message to Devin session {session_id}",
            status_label=SENDING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            session = await self.sessions.get(session_id)
        except httpx.HTTPError as error:
            raise DevinApiError.from_http_error(
                error, f"Failed to read Devin session {session_id}"
            ) from error

        if has_pending_tag(session.tags):
            raise SessionBusyError(
                f"Session {session_id} already has a Port run waiting on it; "
                "wait for that run to finish before sending another message"
            )
        state = classify(session.status, session.status_detail)
        if state.outcome is TurnOutcome.IN_PROGRESS:
            raise SessionBusyError(
                f"Session {session_id} is still working ({state.label}); "
                "wait for Devin to finish before sending another message"
            )

        message_as_user_id = await resolve_user_id(
            self.sessions, inputs.messageAsUserEmail, run
        )
        external_id = build_external_id(run.id)
        sent_at = int(time.time())

        if inputs.reportCompletion:
            try:
                await self.sessions.append_tags(
                    session_id, tracking_tags(installation_id(), external_id, sent_at)
                )
            except httpx.HTTPError as error:
                raise DevinApiError.from_http_error(
                    error,
                    f"Failed to tag Devin session {session_id} for tracking; "
                    "the message was not sent",
                ) from error

        body = merge_config(
            inputs.config,
            {"message": inputs.message, "message_as_user_id": message_as_user_id},
        )
        try:
            session = await self.sessions.send_message(session_id, body)
        except httpx.HTTPError as error:
            if inputs.reportCompletion:
                await self._untrack(session_id)
            raise DevinApiError.from_http_error(
                error, f"Failed to send the message to Devin session {session_id}"
            ) from error

        logger.info(
            f"Sent a message to Devin session {session_id} for run {run.id}",
            session_id=session_id,
            external_id=external_id,
        )
        await ocean.port_client.post_run_log(
            run, f"Devin session turn started: {session.url}", should_raise=False
        )
        await ocean.port_client.update_run_started(
            run,
            session.url,
            external_id,
            extra_output=started_output(session, sent_at),
            status_label=SESSION_RUNNING_STATUS_LABEL,
        )
        await self.register_entity(ObjectKind.SESSION, session.raw(), run)

        if not inputs.reportCompletion:
            await ocean.port_client.report_run_completed(
                run,
                True,
                f"Message sent to Devin session {session_id}",
                status_label=MESSAGE_SENT_STATUS_LABEL,
            )

    async def _untrack(self, session_id: str) -> None:
        """Best effort; a leftover tag is stripped by the tracker once its run is gone."""
        try:
            tags = (await self.sessions.get(session_id)).tags
            await self.sessions.replace_tags(
                session_id, strip_tracking_tags(tags, installation_id())
            )
        except httpx.HTTPError as error:
            logger.warning(
                f"Failed to remove tracking tags from Devin session {session_id}: {error}"
            )
