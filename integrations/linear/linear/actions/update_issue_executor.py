from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.types import UpdateIssuePayload
from linear.actions.utils import set_issue_run_output
from linear.core.mutations import IssueMutations
from linear.helpers.exceptions import MissingExecutionPropertyError


class UpdateIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "update_issue"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_id = run.execution_properties.get("issueId")
        return str(issue_id) if issue_id else None

    async def execute(self, run: IntegrationRun) -> None:
        payload = UpdateIssuePayload.from_execution_properties(run.execution_properties)
        if not payload.to_payload():
            raise MissingExecutionPropertyError(
                "At least one update field is required (title, description, assigneeId, stateId, projectId, cycleId, priority, delegateId, or labelIds)"
            )

        await ocean.port_client.post_run_log(
            run,
            f"Updating issue {payload.issueId}",
            status_label="Updating issue",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        issue = await mutations.update_issue(
            payload.issueId, payload.to_mutation()
        )
        message = f"Updated issue {issue['identifier']}: {issue['url']}"
        set_issue_run_output(run, issue)

        logger.info("Updated Linear issue", issue_id=issue["id"])
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue updated",
        )
