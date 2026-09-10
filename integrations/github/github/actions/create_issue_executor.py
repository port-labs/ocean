import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import IssueActionError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException


class CreateIssueExecutor(AbstractGithubExecutor):
    ACTION_NAME = "create_issue"
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
        title = run.execution_properties.get("title")

        if not (org and repo and title):
            raise InvalidActionParametersException("org, repo, and title are required")

        rest_client = (await self._get_execution_clients(run))[0]
        if not isinstance(rest_client, GithubRestClient):
            raise InvalidActionParametersException("GitHub REST client is required")

        await ocean.port_client.post_run_log(
            run,
            f"Creating issue '{title}' in {org}/{repo}",
            should_raise=False,
        )

        # https://docs.github.com/en/rest/issues/issues#create-an-issue
        issue_body: dict[str, str | list[str]] = {"title": title}
        body = run.execution_properties.get("body")
        if body:
            issue_body["body"] = body
        labels = run.execution_properties.get("labels")
        if labels:
            issue_body["labels"] = labels
        assignees = run.execution_properties.get("assignees")
        if assignees:
            issue_body["assignees"] = assignees

        try:
            issue = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/issues",
                method="POST",
                json_data=issue_body,
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise IssueActionError.from_response(
                e.response, f"Could not create issue in {org}/{repo}"
            )

        if not issue or "number" not in issue or "html_url" not in issue:
            logger.warning(
                f"Received empty or incomplete response from GitHub for issue creation in {org}/{repo}",
                org=org,
                repo=repo,
            )
            raise IssueActionError(
                "Failed to create issue: upstream returned an empty or incomplete response"
            )

        logger.info(
            f"Created issue #{issue['number']} in {org}/{repo}",
            issue_number=issue["number"],
            html_url=issue["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Issue #{issue['number']} created: {issue['html_url']}",
        )
