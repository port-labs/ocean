import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import IssueActionError
from github.actions.utils import build_close_issue_patch_body
from github.helpers.exceptions import InvalidActionParametersException


class CloseIssueExecutor(AbstractGithubExecutor):
    ACTION_NAME = "close_issue"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        issue_number = run.execution_properties.get("issueNumber")

        if not (org and repo and issue_number):
            raise InvalidActionParametersException(
                "org, repo, and issueNumber are required"
            )

        rest_client = await self._get_rest_client(run)

        patch_body = build_close_issue_patch_body(run.execution_properties)

        await ocean.port_client.post_run_log(
            run,
            f"Closing issue #{issue_number} in {org}/{repo} as {patch_body['state_reason']}",
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
                f"Could not close issue #{issue_number} in {org}/{repo}",
            )
        except Exception as e:
            raise IssueActionError(
                f"Could not close issue #{issue_number} in {org}/{repo}: {e}"
            )

        if not issue or "number" not in issue or "html_url" not in issue:
            logger.warning(
                f"Received empty or incomplete response from GitHub for issue close in {org}/{repo}",
                org=org,
                repo=repo,
                issue_number=issue_number,
            )
            raise IssueActionError(
                "Failed to close issue: upstream returned an empty or incomplete response"
            )

        logger.info(
            f"Closed issue #{issue['number']} in {org}/{repo}",
            issue_number=issue["number"],
            html_url=issue["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Issue #{issue['number']} closed: {issue['html_url']}",
        )
