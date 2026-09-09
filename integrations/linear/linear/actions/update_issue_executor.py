from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import build_issue_update_input, require_property
from linear.core.mutations import IssueMutations
from linear.helpers.exceptions import MissingExecutionPropertyError


class UpdateIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "update_issue"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_id = run.execution_properties.get("issueId")
        return str(issue_id) if issue_id else None

    async def execute(self, run: IntegrationRun) -> None:
        issue_id = require_property(run, "issueId")
        issue_input = build_issue_update_input(run.execution_properties)
        if not issue_input:
            raise MissingExecutionPropertyError(
                "At least one update field is required (title, description, assigneeId, stateId, projectId, cycleId, priority, estimate, dueDate, delegateId, or labelIds)"
            )

        await ocean.port_client.post_run_log(
            run,
            f"Updating issue {issue_id}",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        issue = await mutations.update_issue(issue_id, issue_input)

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Updated issue {issue['identifier']}: {issue['url']}",
        )
        logger.info("Updated Linear issue", issue_id=issue["id"])
