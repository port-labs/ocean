import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from pydantic import Field

from actions.abstract_action_input import AbstractDevinActionInput
from actions.abstract_executor import AbstractDevinExecutor
from actions.exceptions import DevinApiError
from actions.utils import installation_id
from clients.models import SessionResponse
from core.tracking.tags import parse_external_id, strip_tracking_tags
from integration import ObjectKind

TERMINATING_STATUS_LABEL = "Terminating session"
SESSION_TERMINATED_STATUS_LABEL = "Session terminated"
TERMINATED_STATUS_LABEL = "Terminated"


class TerminateSessionInputs(AbstractDevinActionInput):
    sessionId: str = Field(min_length=1)
    archive: bool = False


class TerminateSessionExecutor(AbstractDevinExecutor):
    """Executor for the `terminate_session` action.

    A run still waiting on the session is failed here rather than left to the
    `SessionTracker`, which would otherwise read the terminated session's
    `exit` status as a successful turn.
    """

    ACTION_NAME = "terminate_session"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return run.execution_properties.get("sessionId")

    async def execute(self, run: IntegrationRun) -> None:
        inputs = TerminateSessionInputs.from_execution_properties(
            run.execution_properties
        )
        session_id = inputs.sessionId

        await ocean.port_client.post_run_log(
            run,
            f"Terminating Devin session {session_id}",
            status_label=TERMINATING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            tags = (await self.sessions.get(session_id)).tags
            session = await self.sessions.terminate(session_id, inputs.archive)
        except httpx.HTTPError as error:
            raise DevinApiError.from_http_error(
                error, f"Failed to terminate Devin session {session_id}"
            ) from error

        await self._fail_waiting_run(session, tags, run)
        await self.register_entity(ObjectKind.SESSION, session.raw(), run)
        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Terminated Devin session {session_id}",
            status_label=SESSION_TERMINATED_STATUS_LABEL,
        )

    async def _fail_waiting_run(
        self, session: SessionResponse, tags: list[str], run: IntegrationRun
    ) -> None:
        external_id = parse_external_id(tags)
        if external_id is None:
            return
        waiting_run = await ocean.port_client.find_run_by_external_id(external_id)
        if waiting_run is not None and ocean.port_client.is_run_in_progress(
            waiting_run
        ):
            await ocean.port_client.report_run_completed(
                waiting_run,
                False,
                f"Devin session {session.session_id} was terminated by run {run.id}",
                status_label=TERMINATED_STATUS_LABEL,
            )
        try:
            await self.sessions.replace_tags(
                session.session_id, strip_tracking_tags(tags, installation_id())
            )
        except httpx.HTTPError as error:
            logger.warning(
                f"Failed to remove tracking tags from Devin session "
                f"{session.session_id}: {error}"
            )
