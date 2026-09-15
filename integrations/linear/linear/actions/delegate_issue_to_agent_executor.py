from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.types import DelegateIssuePayload
from linear.actions.utils import set_issue_run_output
from linear.core.mutations import IssueMutations


class DelegateIssueToAgentExecutor(AbstractLinearExecutor):
    ACTION_NAME = "delegate_issue_to_agent"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_id = run.execution_properties.get("issueId")
        return str(issue_id) if issue_id else None

    async def execute(self, run: IntegrationRun) -> None:
        payload = DelegateIssuePayload.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Delegating issue {payload.issueId} to agent {payload.delegateId}",
            status_label="Delegating issue",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        issue = await mutations.update_issue(payload.issueId, payload.to_mutation())
        message = f"Delegated issue {issue.identifier} to agent {payload.delegateId}"
        set_issue_run_output(run, issue)

        logger.info(
            "Delegated Linear issue to agent",
            issue_id=issue.id,
            delegate_id=payload.delegateId,
        )
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue delegated",
        )
