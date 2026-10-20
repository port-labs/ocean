import httpx
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from pydantic import Field

from actions.abstract_action_input import AbstractDevinActionInput
from actions.abstract_executor import AbstractDevinExecutor
from actions.exceptions import DevinApiError
from integration import ObjectKind

ARCHIVING_STATUS_LABEL = "Archiving session"
SESSION_ARCHIVED_STATUS_LABEL = "Session archived"


class ArchiveSessionInputs(AbstractDevinActionInput):
    sessionId: str = Field(min_length=1)


class ArchiveSessionExecutor(AbstractDevinExecutor):
    """Executor for the `archive_session` action. Completes synchronously."""

    ACTION_NAME = "archive_session"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return run.execution_properties.get("sessionId")

    async def execute(self, run: IntegrationRun) -> None:
        inputs = ArchiveSessionInputs.from_execution_properties(
            run.execution_properties
        )
        session_id = inputs.sessionId

        await ocean.port_client.post_run_log(
            run,
            f"Archiving Devin session {session_id}",
            status_label=ARCHIVING_STATUS_LABEL,
            should_raise=False,
        )
        try:
            session = await self.sessions.archive(session_id)
        except httpx.HTTPError as error:
            raise DevinApiError.from_http_error(
                error, f"Failed to archive Devin session {session_id}"
            ) from error

        await self.register_entity(ObjectKind.SESSION, session.raw(), run)
        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Archived Devin session {session_id}",
            status_label=SESSION_ARCHIVED_STATUS_LABEL,
        )
