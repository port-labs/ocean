from __future__ import annotations

import asyncio

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from factory_ai.actions.abstract_executor import AbstractFactoryExecutor
from factory_ai.actions.exceptions import ExecuteDroidError
from factory_ai.actions.execute_droid.models import (
    ExecuteDroidResponse,
    ListSessionMessagesResponse,
    has_assistant_message_after,
    parse_execute_droid_inputs,
)
from factory_ai.clients.exceptions import FactoryAIError
from factory_ai.config import DEFAULT_FACTORY_APP_HOST
from factory_ai.core.exporters.session.exporter import SessionExporter
from factory_ai.core.exporters.session.models import GetSessionOptions, Session
from factory_ai.kinds import ObjectKind

DROID_EXECUTE_PATH = "/api/v0/droid/execute"
EXECUTING_STATUS_LABEL = "Executing droid"
EXECUTE_FAILED_STATUS_LABEL = "Execute failed"
TURN_ACCEPTED_STATUS_LABEL = "Turn accepted"
TURN_RUNNING_STATUS_LABEL = "Turn running"
TURN_COMPLETED_STATUS_LABEL = "Turn completed"
TURN_TIMED_OUT_STATUS_LABEL = "Timed out"

POLL_INTERVAL_SECONDS = 5.0
MAX_POLL_ATTEMPTS = 120  # 10 minutes at the default interval
MESSAGES_PAGE_LIMIT = 50


class ExecuteDroidExecutor(AbstractFactoryExecutor):
    """Executor for the ``execute_droid`` action.

    Calls ``POST /api/v0/droid/execute``, which returns **202 Accepted** once
    Factory has accepted the turn. Factory has no outbound webhooks.

    When ``waitForCompletion`` is true (default), the Port run stays open and
    the executor polls until the turn is done: session ``status`` is ``idle``
    and messages include an assistant reply after the returned ``messageId``.
    Idle alone is not enough — status can still show the previous turn as idle
    right after execute.

    When ``waitForCompletion`` is false, the Port run completes immediately
    after the 202 with session/message/computer ids and app links.
    """

    ACTION_NAME = "execute_droid"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        # Continuations on one session must not race; new sessions may run in parallel.
        session_id = run.execution_properties.get("sessionId")
        if isinstance(session_id, str) and session_id:
            return session_id
        return None

    async def execute(self, run: IntegrationRun) -> None:
        inputs = parse_execute_droid_inputs(run.execution_properties)
        body = inputs.to_request_body()

        await ocean.port_client.post_run_log(
            run,
            (
                f"Executing Droid turn on {inputs.targetKind} "
                f"(prompt length {len(inputs.prompt)})"
            ),
            status_label=EXECUTING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            response = await self.client.post(
                DROID_EXECUTE_PATH,
                ExecuteDroidResponse,
                json_body=body,
            )
        except httpx.HTTPStatusError as error:
            raise ExecuteDroidError.from_response(
                error.response,
                f"Could not execute Droid turn on {inputs.targetKind}",
            ) from error
        except FactoryAIError as error:
            raise ExecuteDroidError(
                f"Could not execute Droid turn on {inputs.targetKind}: {error}",
                status_label=EXECUTE_FAILED_STATUS_LABEL,
            ) from error

        session_url = f"{DEFAULT_FACTORY_APP_HOST}/sessions/{response.session_id}"
        computer_url = f"{DEFAULT_FACTORY_APP_HOST}/computers/{response.computer_id}"

        logger.info(
            f"Accepted Droid turn for session {response.session_id} "
            f"(message {response.message_id}, computer {response.computer_id}) "
            f"for Port run {run.id}"
        )

        await self._reflect_session(response.session_id, response.computer_id, run)

        output = {
            "sessionId": response.session_id,
            "computerId": response.computer_id,
            "messageId": response.message_id,
            "sessionUrl": session_url,
            "computerUrl": computer_url,
        }
        if isinstance(run, WorkflowNodeRun):
            run.output.update(output)

        if not inputs.waitForCompletion:
            await ocean.port_client.report_run_completed(
                run,
                True,
                (
                    f"Droid turn accepted (202). sessionId={response.session_id}, "
                    f"messageId={response.message_id}, computerId={response.computer_id}. "
                    f"Session: {session_url}."
                ),
                status_label=TURN_ACCEPTED_STATUS_LABEL,
            )
            return

        await ocean.port_client.update_run_started(
            run,
            session_url,
            response.message_id,
            extra_output=output,
            status_label=TURN_RUNNING_STATUS_LABEL,
        )
        await ocean.port_client.post_run_log(
            run,
            (
                f"Waiting for turn completion on session {response.session_id} "
                f"(message {response.message_id})"
            ),
            status_label=TURN_RUNNING_STATUS_LABEL,
            should_raise=False,
        )

        await self._wait_for_turn_completion(
            response.session_id, response.computer_id, response.message_id
        )
        await self._reflect_session(response.session_id, response.computer_id, run)

        await ocean.port_client.report_run_completed(
            run,
            True,
            (
                f"Droid turn completed. sessionId={response.session_id}, "
                f"messageId={response.message_id}. Session: {session_url}."
            ),
            status_label=TURN_COMPLETED_STATUS_LABEL,
        )

    async def _wait_for_turn_completion(
        self, session_id: str, computer_id: str, user_message_id: str
    ) -> None:
        """Poll until session is idle and an assistant message follows ``user_message_id``."""
        for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
            if await self._is_turn_complete(session_id, computer_id, user_message_id):
                logger.info(
                    f"Droid turn complete for session {session_id} "
                    f"after {attempt} poll(s)"
                )
                return

            if attempt < MAX_POLL_ATTEMPTS:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        raise ExecuteDroidError(
            (
                f"Timed out waiting for Droid turn on session {session_id} "
                f"(message {user_message_id}) after "
                f"{int(MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS)}s"
            ),
            status_label=TURN_TIMED_OUT_STATUS_LABEL,
        )

    async def _is_turn_complete(
        self, session_id: str, computer_id: str, user_message_id: str
    ) -> bool:
        try:
            session = await self.client.get(
                f"/api/v0/sessions/{session_id}",
                Session,
                params={"computerId": computer_id},
            )
        except (httpx.HTTPStatusError, FactoryAIError) as error:
            logger.warning(
                f"Failed to poll session {session_id} while waiting for completion: {error}"
            )
            return False

        if session.status != "idle":
            return False

        try:
            messages_response = await self.client.get(
                f"/api/v0/sessions/{session_id}/messages",
                ListSessionMessagesResponse,
                params={"computerId": computer_id, "limit": MESSAGES_PAGE_LIMIT},
            )
        except (httpx.HTTPStatusError, FactoryAIError) as error:
            logger.warning(
                f"Failed to poll messages for session {session_id} "
                f"while waiting for completion: {error}"
            )
            return False

        return has_assistant_message_after(messages_response.messages, user_message_id)

    async def _reflect_session(
        self, session_id: str, computer_id: str, run: IntegrationRun
    ) -> None:
        """Best-effort catalog upsert for the session created/continued by execute."""
        try:
            exporter = SessionExporter(self.client)
            raw = await exporter.get_resource(
                GetSessionOptions(session_id=session_id, computer_id=computer_id)
            )
        except Exception as error:
            logger.warning(
                f"Failed to fetch session {session_id} after execute (continuing): {error}"
            )
            return
        if raw is None:
            logger.warning(
                f"Session {session_id} not readable yet after execute (continuing)"
            )
            return
        await self.register_entity(ObjectKind.SESSION, raw, run)
