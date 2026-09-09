from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import require_property
from linear.core.mutations import IssueMutations


class DelegateIssueToAgentExecutor(AbstractLinearExecutor):
    ACTION_NAME = "delegate_issue_to_agent"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_id = run.execution_properties.get("issueId")
        return str(issue_id) if issue_id else None

    async def execute(self, run: IntegrationRun) -> None:
        issue_id = require_property(run, "issueId")
        delegate_id = require_property(run, "delegateId")

        await ocean.port_client.post_run_log(
            run,
            f"Delegating issue {issue_id} to agent {delegate_id}",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        issue = await mutations.update_issue(issue_id, {"delegateId": str(delegate_id)})

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Delegated issue {issue['identifier']} to agent {delegate_id}",
        )
        logger.info(
            "Delegated Linear issue to agent",
            issue_id=issue["id"],
            delegate_id=delegate_id,
        )
