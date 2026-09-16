from typing import Any

import httpx
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import MergePullRequestError


class MergePullRequestInputs(AbstractGithubActionInput):
    org: str
    repo: str
    prNumber: int
    mergeMethod: str
    commitTitle: str | None = None
    commitMessage: str | None = None


class MergePullRequestExecutor(AbstractGithubExecutor):
    ACTION_NAME = "merge_pull_request"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = MergePullRequestInputs.from_execution_properties(
            run.execution_properties
        )

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Merging pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo} ({inputs.mergeMethod})",
            status_label="Merging pull request",
            should_raise=False,
        )

        merge_body: dict[str, Any] = {"merge_method": inputs.mergeMethod}
        if inputs.commitTitle is not None:
            merge_body["commit_title"] = inputs.commitTitle
        if inputs.commitMessage is not None:
            merge_body["commit_message"] = inputs.commitMessage

        try:
            result = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{inputs.org}/{inputs.repo}/pulls/{inputs.prNumber}/merge",
                method="PUT",
                json_data=merge_body,
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise MergePullRequestError.from_response(
                e.response,
                f"Could not merge pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo}",
            )

        if not result.get("merged"):
            raise MergePullRequestError(
                f"Failed to merge pull request #{inputs.prNumber}: {result.get('message', 'unknown reason')}"
            )

        logger.info(
            f"Merged pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo}",
            pr_number=inputs.prNumber,
            merge_sha=result["sha"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Pull request #{inputs.prNumber} merged via {inputs.mergeMethod}",
            status_label="Pull request merged",
        )
