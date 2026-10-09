from typing import Any

import httpx
from loguru import logger
from pydantic import Field
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from jira.actions.abstract_jira_action_input import AbstractJiraActionInput
from jira.actions.abstract_jira_executor import AbstractJiraExecutor
from jira.actions.exceptions import MissingExecutionPropertyError, UpdateIssueError
from jira.actions.utils import plain_text_adf


class UpdateIssueInput(AbstractJiraActionInput):
    issue_key: str = Field(..., alias="issueKey", min_length=1)
    summary: str | None = None
    description: str | None = None
    priority: str | None = None
    assignee_account_id: str | None = Field(default=None, alias="assigneeAccountId")
    fields: dict[str, Any] | None = None

    def to_api_payload(self) -> dict[str, Any]:
        field_updates: dict[str, Any] = {}
        if self.summary:
            field_updates["summary"] = self.summary
        if self.description:
            field_updates["description"] = plain_text_adf(self.description)
        if self.priority:
            field_updates["priority"] = {"name": self.priority}
        if self.assignee_account_id:
            field_updates["assignee"] = {"id": self.assignee_account_id}
        if self.fields:
            field_updates.update(self.fields)
        if not field_updates:
            raise MissingExecutionPropertyError(
                "At least one field must be provided to update"
            )
        return {"fields": field_updates}


class UpdateIssueExecutor(AbstractJiraExecutor):
    ACTION_NAME = "update_issue"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        issue_key = run.execution_properties.get("issueKey")
        return str(issue_key) if issue_key else None

    async def execute(self, run: IntegrationRun) -> None:
        action_input = UpdateIssueInput.from_execution_properties(
            run.execution_properties
        )
        payload = action_input.to_api_payload()

        await ocean.port_client.post_run_log(
            run,
            f"Updating Jira issue {action_input.issue_key}",
            status_label="Updating issue",
            should_raise=False,
        )

        try:
            await self.client.update_issue(action_input.issue_key, payload)
        except httpx.HTTPStatusError as error:
            raise UpdateIssueError.from_response(
                error.response,
                f"Could not update issue '{action_input.issue_key}'",
            )

        logger.info(
            "Updated Jira issue",
            issue_key=action_input.issue_key,
            updated_fields=list(payload["fields"].keys()),
        )

        await self._complete_issue_action(
            run,
            issue_key=action_input.issue_key,
            message=f"Updated issue {action_input.issue_key}",
            status_label="Issue updated",
            output={"updatedFields": list(payload["fields"].keys())},
        )
