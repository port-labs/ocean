from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import require_property
from linear.core.mutations import IssueMutations


class DeleteIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "delete_issue"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_id = run.execution_properties.get("issueId")
        return str(issue_id) if issue_id else None

    async def execute(self, run: IntegrationRun) -> None:
        issue_id = require_property(run, "issueId")

        await ocean.port_client.post_run_log(
            run,
            f"Deleting issue {issue_id}",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        await mutations.delete_issue(issue_id)

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Deleted issue {issue_id}",
        )
        logger.info("Deleted Linear issue", issue_id=issue_id)
