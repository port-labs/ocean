from typing import Any

import httpx
from loguru import logger
from pydantic import Field
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from jira.actions.abstract_jira_action_input import AbstractJiraActionInput
from jira.actions.abstract_jira_executor import AbstractJiraExecutor
from jira.actions.exceptions import CreateIssueError
from jira.actions.utils import plain_text_adf


class CreateIssueInput(AbstractJiraActionInput):
    project: str = Field(..., min_length=1)
    issue_type: str = Field(..., alias="issueType", min_length=1)
    summary: str = Field(..., min_length=1)
    description: str | None = None
    priority: str | None = None
    assignee_account_id: str | None = Field(default=None, alias="assigneeAccountId")

    def to_api_payload(self) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "project": {"key": self.project},
            "issuetype": {"name": self.issue_type},
            "summary": self.summary,
        }
        if self.description:
            fields["description"] = plain_text_adf(self.description)
        if self.priority:
            fields["priority"] = {"name": self.priority}
        if self.assignee_account_id:
            fields["assignee"] = {"id": self.assignee_account_id}
        return {"fields": fields}


class CreateIssueExecutor(AbstractJiraExecutor):
    ACTION_NAME = "create_issue"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        action_input = CreateIssueInput.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Creating Jira issue in project {action_input.project}",
            status_label="Creating issue",
            should_raise=False,
        )

        try:
            created_issue = await self.client.create_issue(
                action_input.to_api_payload()
            )
        except httpx.HTTPStatusError as error:
            raise CreateIssueError.from_response(
                error.response,
                f"Could not create issue in project '{action_input.project}'",
            )

        issue_key = created_issue.get("key")
        if not issue_key:
            raise CreateIssueError(
                "Failed to create issue: Jira returned an empty or incomplete response"
            )

        logger.info(
            "Created Jira issue",
            issue_key=issue_key,
            project=action_input.project,
            issue_type=action_input.issue_type,
        )

        await self._complete_issue_action(
            run,
            issue_key=issue_key,
            message=f"Created issue {issue_key}",
            status_label="Issue created",
            output={"issueId": str(created_issue.get("id"))},
        )
