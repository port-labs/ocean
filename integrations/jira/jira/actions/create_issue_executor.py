import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from jira.actions.abstract_jira_executor import AbstractJiraExecutor
from jira.actions.exceptions import CreateIssueError, MissingExecutionPropertyError
from jira.actions.utils import build_create_issue_payload, get_issue_browse_url


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

        payload = build_create_issue_payload(
            project=project,
            issue_type=issue_type,
            summary=summary,
            description=description,
            priority=priority,
            assignee_account_id=assignee_account_id,
        )

        try:
            created_issue = await self.client.create_issue(payload)
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

        issue_link = get_issue_browse_url(
            self.client.jira_url,
            issue_key,
            oauth_enabled=self.client.is_oauth_enabled(),
        )
        message = f"Created issue {issue_key}"
        if issue_link:
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
