from __future__ import annotations

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from factory_ai.actions.abstract_executor import AbstractFactoryExecutor
from factory_ai.actions.exceptions import ExecuteDroidError
from factory_ai.actions.execute_droid.models import (
    ExecuteDroidResponse,
    parse_execute_droid_inputs,
)
from factory_ai.clients.exceptions import FactoryAIError
from factory_ai.config import DEFAULT_FACTORY_APP_HOST
from factory_ai.core.exporters.session.exporter import SessionExporter
from factory_ai.core.exporters.session.models import GetSessionOptions
from factory_ai.kinds import ObjectKind

DROID_EXECUTE_PATH = "/api/v0/droid/execute"
EXECUTING_STATUS_LABEL = "Executing droid"
EXECUTE_FAILED_STATUS_LABEL = "Execute failed"
TURN_ACCEPTED_STATUS_LABEL = "Turn accepted"


class ExecuteDroidExecutor(AbstractFactoryExecutor):
    """Executor for the ``execute_droid`` action.

    Calls ``POST /api/v0/droid/execute``, which returns **202 Accepted** once
    Factory has accepted the turn — not when the assistant finishes. Factory
    has no outbound webhooks, so this action completes the Port run after the
    202 response with session/message/computer ids and app links.

    To detect turn completion yourself:

    1. Poll ``GET /api/v0/sessions/{sessionId}`` until ``status`` is ``idle``.
       Do not treat the first ``idle`` immediately after execute as done — the
       previous turn may still be reflected briefly.
    2. Confirm ``GET /api/v0/sessions/{sessionId}/messages`` contains an
       assistant message after the user message whose ``id`` is the returned
       ``messageId``.
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

        await ocean.port_client.report_run_completed(
            run,
            True,
            (
                f"Droid turn accepted (202). sessionId={response.session_id}, "
                f"messageId={response.message_id}, computerId={response.computer_id}. "
                f"Session: {session_url}. "
                "Factory has no completion webhooks; poll session status until idle "
                "and confirm an assistant message after messageId for turn completion."
            ),
            status_label=TURN_ACCEPTED_STATUS_LABEL,
        )

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
