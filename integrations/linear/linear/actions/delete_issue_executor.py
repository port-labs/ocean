from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.types import DeleteIssuePayload
from linear.actions.utils import set_issue_id_run_output
from linear.core.mutations import IssueMutations


class DeleteIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "delete_issue"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_id = run.execution_properties.get("issueId")
        return str(issue_id) if issue_id else None

    async def execute(self, run: IntegrationRun) -> None:
        payload = DeleteIssuePayload.from_execution_properties(run.execution_properties)

        await ocean.port_client.post_run_log(
            run,
            f"Deleting issue {payload.issueId}",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        await mutations.delete_issue(payload.issueId)

        set_issue_id_run_output(run, payload.issueId)
        logger.info("Deleted Linear issue", issue_id=payload.issueId)
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Deleted issue {payload.issueId}",
            status_label="Issue deleted",
        )
