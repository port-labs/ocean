from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import PullRequestActionError
from github.helpers.exceptions import InvalidActionParametersException


class MergePullRequestExecutor(AbstractGithubExecutor):
    ACTION_NAME = "merge_pull_request"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        pr_number = run.execution_properties.get("prNumber")
        merge_method = run.execution_properties.get("mergeMethod")

        if not (org and repo and pr_number and merge_method):
            raise InvalidActionParametersException(
                "org, repo, prNumber, and mergeMethod are required"
            )

        rest_client = await self._get_rest_client(run)

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
            raise PullRequestActionError.from_response(
                e.response, f"Could not merge pull request #{pr_number} in {org}/{repo}"
            )
        except Exception as e:
            raise PullRequestActionError(
                f"Could not merge pull request #{pr_number} in {org}/{repo}: {e}"
            )

        if not result["merged"]:
            raise PullRequestActionError(
                f"Failed to merge pull request #{pr_number}: {result['message']}"
            )

        logger.info(
            f"Merged pull request #{pr_number} in {org}/{repo}",
            pr_number=pr_number,
            merge_sha=result["sha"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Pull request #{pr_number} merged via {merge_method}",
        )
