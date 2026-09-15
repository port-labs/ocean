from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.types import ArchiveIssuePayload
from linear.core.mutations import IssueMutations


class ArchiveIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "archive_issue"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_id = run.execution_properties.get("issueId")
        return str(issue_id) if issue_id else None

    async def execute(self, run: IntegrationRun) -> None:
        payload = ArchiveIssuePayload.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Archiving issue {payload.issueId}",
            status_label="Archiving issue",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        await mutations.archive_issue(payload.issueId)

        logger.info("Archived Linear issue", issue_id=payload.issueId)
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Archived issue {payload.issueId}",
            status_label="Issue archived",
        )
