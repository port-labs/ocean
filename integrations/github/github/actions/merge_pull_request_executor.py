from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_pull_request_executor import AbstractPullRequestExecutor
from github.actions.exceptions import MergePullRequestError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException

# https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request
VALID_MERGE_METHODS = frozenset({"merge", "squash", "rebase"})


class MergePullRequestExecutor(AbstractPullRequestExecutor):
    ACTION_NAME = "merge_pull_request"

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        pr_number = run.execution_properties.get("prNumber")

        if not (org and repo and pr_number):
            raise InvalidActionParametersException(
                "org, repo, and prNumber are required"
            )

        merge_method = run.execution_properties.get("mergeMethod", "merge")
        if merge_method not in VALID_MERGE_METHODS:
            raise InvalidActionParametersException(
                f"mergeMethod must be one of: {', '.join(sorted(VALID_MERGE_METHODS))}"
            )

        rest_client = (await self._get_execution_clients(run))[0]
        if not isinstance(rest_client, GithubRestClient):
            raise InvalidActionParametersException("GitHub REST client is required")

        await ocean.port_client.post_run_log(
            run,
            f"Merging pull request #{pr_number} in {org}/{repo} ({merge_method})",
            should_raise=False,
        )

        merge_body: dict[str, Any] = {"merge_method": merge_method}
        commit_title = run.execution_properties.get("commitTitle")
        if commit_title:
            merge_body["commit_title"] = commit_title
        commit_message = run.execution_properties.get("commitMessage")
        if commit_message:
            merge_body["commit_message"] = commit_message

        try:
            result = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/pulls/{pr_number}/merge",
                method="PUT",
                json_data=merge_body,
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise MergePullRequestError.from_response(
                e.response, f"Could not merge pull request #{pr_number} in {org}/{repo}"
            )

        if not result or not result.get("merged"):
            message = (
                result.get("message", "Unknown error") if result else "Empty response"
            )
            raise MergePullRequestError(
                f"Failed to merge pull request #{pr_number}: {message}"
            )

        pr_url = f"https://github.com/{org}/{repo}/pull/{pr_number}"
        logger.info(
            f"Merged pull request #{pr_number} in {org}/{repo}",
            pr_number=pr_number,
            merge_sha=result["sha"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Pull request #{pr_number} merged: {pr_url}",
        )
