from __future__ import annotations

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from factory_ai.actions.abstract_executor import AbstractFactoryExecutor
from factory_ai.actions.exceptions import InterruptSessionError
from factory_ai.actions.interrupt_session.models import (
    InterruptSessionInputs,
    InterruptSessionResponse,
)
from factory_ai.clients.exceptions import FactoryAIError
from factory_ai.config import DEFAULT_FACTORY_APP_HOST

INTERRUPT_FAILED_STATUS_LABEL = "Interrupt failed"
INTERRUPTING_STATUS_LABEL = "Interrupting session"
SESSION_INTERRUPTED_STATUS_LABEL = "Session interrupted"


class InterruptSessionExecutor(AbstractFactoryExecutor):
    """Executor for the ``interrupt_session`` action.

    Calls ``POST /api/v0/sessions/{sessionId}/interrupt``. Factory stops the
    running agent loop and returns the session's current execution status. The
    call is idempotent when the session is already idle.
    """

    ACTION_NAME = "interrupt_session"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        session_id = run.execution_properties.get("sessionId")
        if isinstance(session_id, str) and session_id:
            return session_id
        return None

    async def execute(self, run: IntegrationRun) -> None:
        inputs = InterruptSessionInputs.from_execution_properties(
            run.execution_properties
        )
        session_id = inputs.sessionId
        interrupt_path = f"/api/v0/sessions/{session_id}/interrupt"

        await ocean.port_client.post_run_log(
            run,
            f"Interrupting Factory session {session_id}",
            status_label=INTERRUPTING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            response = await self.client.post(
                interrupt_path,
                InterruptSessionResponse,
            )
        except httpx.HTTPStatusError as error:
            raise InterruptSessionError.from_response(
                error.response,
                f"Could not interrupt session {session_id}",
            ) from error
        except FactoryAIError as error:
            raise InterruptSessionError(
                f"Could not interrupt session {session_id}: {error}",
                status_label=INTERRUPT_FAILED_STATUS_LABEL,
            ) from error

        session_url = f"{DEFAULT_FACTORY_APP_HOST}/sessions/{session_id}"
        logger.info(
            f"Interrupted Factory session {session_id} "
            f"(status={response.status}) for Port run {run.id}"
        )

        await self._reflect_session(session_id, run)

        output = {
            "sessionId": session_id,
            "status": response.status,
            "sessionUrl": session_url,
        }
        if isinstance(run, WorkflowNodeRun):
            run.output.update(output)

        await ocean.port_client.report_run_completed(
            run,
            True,
            (
                f"Interrupted session {session_id} "
                f"(status={response.status}). Session: {session_url}."
            ),
            status_label=SESSION_INTERRUPTED_STATUS_LABEL,
        )
