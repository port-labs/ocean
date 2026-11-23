import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from pydantic import Field

from actions.abstract_action_input import AbstractDevinActionInput
from actions.abstract_executor import AbstractDevinExecutor, DevinApiError
from actions.utils import ensure_port_managed_session, upsert_raw_best_effort
from core.tracking.tags import parse_external_id, strip_tracking_tags
from integration import ObjectKind

TERMINATING_STATUS_LABEL = "Terminating session"
SESSION_TERMINATED_STATUS_LABEL = "Session terminated"
TERMINATED_STATUS_LABEL = "Terminated"


class TerminateSessionInputs(AbstractDevinActionInput):
    sessionId: str = Field(min_length=1)
    archive: bool = False


class TerminateSessionExecutor(AbstractDevinExecutor):
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
            current = await self.sessions.get(session_id)
            ensure_port_managed_session(current)
            tags = current.tags
            await self._release_waiting_run(session_id, tags, run)
            session = await self.sessions.terminate(session_id, inputs.archive)
        except httpx.HTTPError as error:
            raise DevinApiError.from_http_error(
                error, f"Failed to terminate Devin session {session_id}"
            ) from error

        await upsert_raw_best_effort(ObjectKind.SESSION, session.raw(), run)
        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Terminated Devin session {session_id}",
            status_label=SESSION_TERMINATED_STATUS_LABEL,
        )

    async def _release_waiting_run(
        self, session_id: str, tags: list[str], run: IntegrationRun
    ) -> None:
        # Fail waiting runs here; the tracker would treat `exit` as a successful turn.
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
                f"Devin session {session_id} was terminated by run {run.id}",
                status_label=TERMINATED_STATUS_LABEL,
            )
        try:
            await self.sessions.replace_tags(
                session_id,
                strip_tracking_tags(tags, ocean.config.integration.identifier),
            )
        except httpx.HTTPError as error:
            logger.warning(
                f"Failed to remove tracking tags from Devin session "
                f"{session_id}: {error}"
            )
