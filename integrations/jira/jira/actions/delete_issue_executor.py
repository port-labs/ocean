import httpx
from loguru import logger
from pydantic import Field
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from jira.actions.abstract_jira_action_input import AbstractJiraActionInput
from jira.actions.abstract_jira_executor import AbstractJiraExecutor
from jira.actions.exceptions import DeleteIssueError


class DeleteIssueInput(AbstractJiraActionInput):
    issue_key: str = Field(..., alias="issueKey", min_length=1)
    delete_subtasks: bool = Field(default=False, alias="deleteSubtasks")


class DeleteIssueExecutor(AbstractJiraExecutor):
    ACTION_NAME = "delete_issue"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_key = run.execution_properties.get("issueKey")
        return issue_key if issue_key else None

    async def execute(self, run: IntegrationRun) -> None:
        action_input = DeleteIssueInput.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Deleting Jira issue {action_input.issue_key}",
            status_label="Deleting issue",
            should_raise=False,
        )

        try:
            await self.client.delete_issue(
                action_input.issue_key,
                delete_subtasks=action_input.delete_subtasks,
            )
        except httpx.HTTPStatusError as error:
            raise DeleteIssueError.from_response(
                error.response,
                f"Could not delete issue '{action_input.issue_key}'",
            )

        logger.info(
            "Deleted Jira issue",
            issue_key=action_input.issue_key,
            delete_subtasks=action_input.delete_subtasks,
        )

        await self._complete_issue_action(
            run,
            issue_key=action_input.issue_key,
            message=f"Deleted issue {action_input.issue_key}",
            status_label="Issue deleted",
            output={},
        )
