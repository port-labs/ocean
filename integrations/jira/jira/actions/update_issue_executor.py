from typing import Any

import httpx
from loguru import logger
from pydantic import Field
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from jira.actions.abstract_jira_action_input import AbstractJiraActionInput
from jira.actions.abstract_jira_executor import AbstractJiraExecutor
from jira.actions.exceptions import MissingExecutionPropertyError, UpdateIssueError
from jira.actions.utils import get_issue_browse_url, plain_text_adf


class UpdateIssueInput(AbstractJiraActionInput):
    issue_key: str = Field(..., alias="issueKey", min_length=1)
    summary: str | None = None
    description: str | None = None
    priority: str | None = None
    assignee_account_id: str | None = Field(default=None, alias="assigneeAccountId")
    fields: dict[str, Any] | None = None

    def to_api_payload(self) -> dict[str, Any]:
        field_updates: dict[str, Any] = {}
        if self.summary is not None:
            field_updates["summary"] = self.summary
        if self.description is not None:
            field_updates["description"] = plain_text_adf(self.description)
        if self.priority is not None:
            field_updates["priority"] = {"name": self.priority}
        if self.assignee_account_id is not None:
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

        issue_url = get_issue_browse_url(
            self.client.jira_url,
            action_input.issue_key,
            oauth_enabled=self.client.is_oauth_enabled(),
        )
        message = f"Updated issue {action_input.issue_key}"
        if issue_url:
            message = f"{message}: {issue_url}"

        await ocean.port_client.post_run_log(
            run,
            message,
            should_raise=False,
        )
        logger.info(
            "Updated Jira issue",
            issue_key=action_input.issue_key,
            updated_fields=list(payload["fields"].keys()),
        )

        if isinstance(run, WorkflowNodeRun):
            run.output = {
                "issueKey": action_input.issue_key,
                "updatedFields": list(payload["fields"].keys()),
                "issueUrl": issue_url or "",
            }
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Issue updated",
        )
