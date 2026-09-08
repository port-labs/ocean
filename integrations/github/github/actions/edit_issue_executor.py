import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import IssueActionError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException


class EditIssueExecutor(AbstractGithubExecutor):
    ACTION_NAME = "edit_issue"
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

        # https://docs.github.com/en/rest/issues/issues#update-an-issue
        patch_body: dict[str, str | list[str]] = {}
        for key in ("title", "body", "state"):
            value = run.execution_properties.get(key)
            if value is not None:
                patch_body[key] = value
        labels = run.execution_properties.get("labels")
        if labels is not None:
            patch_body["labels"] = labels
        assignees = run.execution_properties.get("assignees")
        if assignees is not None:
            patch_body["assignees"] = assignees

        if not patch_body:
            raise InvalidActionParametersException(
                "At least one field to update is required (title, body, state, labels, or assignees)"
            )

        rest_client = (await self._get_execution_clients(run))[0]
        if not isinstance(rest_client, GithubRestClient):
            raise InvalidActionParametersException("GitHub REST client is required")

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
