from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from jira.actions.abstract_jira_executor import AbstractJiraExecutor
from jira.actions.exceptions import CreateIssueError, MissingExecutionPropertyError


class CreateIssueExecutor(AbstractJiraExecutor):
    ACTION_NAME = "create_issue"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        project = run.execution_properties.get("project")
        issue_type = run.execution_properties.get("issueType")
        summary = run.execution_properties.get("summary")
        description = run.execution_properties.get("description")
        priority = run.execution_properties.get("priority")
        assignee_account_id = run.execution_properties.get("assigneeAccountId")

        if not project:
            raise MissingExecutionPropertyError("project is required")
        if not issue_type:
            raise MissingExecutionPropertyError("issueType is required")
        if not summary:
            raise MissingExecutionPropertyError("summary is required")

        await ocean.port_client.post_run_log(
            run,
            f"Creating Jira issue in project {project}",
            should_raise=False,
        )

        fields: dict[str, Any] = {
            "project": {"key": project},
            "issuetype": {"name": issue_type},
            "summary": summary,
        }
        if description:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            }
        if priority:
            fields["priority"] = {"name": priority}
        if assignee_account_id:
            fields["assignee"] = {"id": assignee_account_id}

        try:
            created_issue = await self.client.create_issue({"fields": fields})
        except httpx.HTTPStatusError as error:
            raise CreateIssueError.from_response(
                error.response,
                f"Could not create issue in project '{project}'",
            )

        issue_key = created_issue.get("key")
        if not issue_key:
            raise CreateIssueError(
                "Failed to create issue: Jira returned an empty or incomplete response"
            )

        message = f"Created issue {issue_key}"
        if not self.client.is_oauth_enabled():
            issue_link = f"{self.client.jira_url.rstrip('/')}/browse/{issue_key}"
            message = f"{message}: {issue_link}"

        await ocean.port_client.post_run_log(
            run,
            message,
            should_raise=False,
        )
        logger.info(
            "Created Jira issue",
            issue_key=issue_key,
            project=project,
            issue_type=issue_type,
        )
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
        )
