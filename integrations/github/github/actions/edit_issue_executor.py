import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import IssueActionError
from github.actions.utils import build_issue_patch_body
from github.helpers.exceptions import InvalidActionParametersException


class EditIssueExecutor(AbstractGithubExecutor):
    ACTION_NAME = "edit_issue"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        issue_number = run.execution_properties.get("issueNumber")

        if not (org and repo and issue_number):
            raise InvalidActionParametersException(
                "org, repo, and issueNumber are required"
            )

        try:
            patch_body = build_issue_patch_body(run)
        except ValueError as e:
            raise InvalidActionParametersException(str(e))

        if not patch_body:
            raise InvalidActionParametersException(
                "At least one field to update is required (title, body, state, labels, assignees, or stateReason)"
            )

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Editing issue #{issue_number} in {org}/{repo}",
            should_raise=False,
        )

        try:
            issue = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/issues/{issue_number}",
                method="PATCH",
                json_data=patch_body,
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise IssueActionError.from_response(
                e.response,
                f"Could not edit issue #{issue_number} in {org}/{repo}",
            )

        if not issue or "number" not in issue or "html_url" not in issue:
            logger.warning(
                f"Received empty or incomplete response from GitHub for issue edit in {org}/{repo}",
                org=org,
                repo=repo,
                issue_number=issue_number,
            )
            raise IssueActionError(
                "Failed to edit issue: upstream returned an empty or incomplete response"
            )

        logger.info(
            f"Edited issue #{issue['number']} in {org}/{repo}",
            issue_number=issue["number"],
            html_url=issue["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Issue #{issue['number']} updated: {issue['html_url']}",
        )
