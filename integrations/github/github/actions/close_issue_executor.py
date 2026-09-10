import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import IssueActionError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException


class CloseIssueExecutor(AbstractGithubExecutor):
    ACTION_NAME = "close_issue"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        if not org or not repo:
            return None
        return f"{org}/{repo}"

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        issue_number = run.execution_properties.get("issueNumber")

        if not (org and repo and issue_number):
            raise InvalidActionParametersException(
                "org, repo, and issueNumber are required"
            )

        rest_client = (await self._get_execution_clients(run))[0]
        if not isinstance(rest_client, GithubRestClient):
            raise InvalidActionParametersException("GitHub REST client is required")

        # https://docs.github.com/en/rest/issues/issues#update-an-issue
        state_reason = run.execution_properties.get("stateReason", "completed")

        await ocean.port_client.post_run_log(
            run,
            f"Closing issue #{issue_number} in {org}/{repo} as {state_reason}",
            should_raise=False,
        )

        try:
            issue = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/issues/{issue_number}",
                method="PATCH",
                json_data={"state": "closed", "state_reason": state_reason},
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise IssueActionError.from_response(
                e.response,
                f"Could not close issue #{issue_number} in {org}/{repo}",
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
