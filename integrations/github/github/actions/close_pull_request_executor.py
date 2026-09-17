import httpx
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import ClosePullRequestError


class ClosePullRequestInputs(AbstractGithubActionInput):
    org: str
    repo: str
    prNumber: int


class ClosePullRequestExecutor(AbstractGithubExecutor):
    ACTION_NAME = "close_pull_request"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = ClosePullRequestInputs.from_execution_properties(
            run.execution_properties
        )

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Closing pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo}",
            status_label="Closing pull request",
            should_raise=False,
        )

        try:
            pr = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{inputs.org}/{inputs.repo}/pulls/{inputs.prNumber}",
                method="PATCH",
                json_data={"state": "closed"},
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise ClosePullRequestError.from_response(
                e.response,
                f"Could not close pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo}",
            )

        pr_number = pr.get("number")
        if pr_number is None:
            raise ClosePullRequestError(
                "Failed to close pull request: GitHub returned an empty or incomplete response"
            )

        message = f"Pull request #{pr_number} closed: {pr['html_url']}"
        logger.info(
            f"Closed pull request #{pr_number} in {inputs.org}/{inputs.repo}",
            pr_number=pr_number,
            html_url=pr["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Pull request closed",
        )
