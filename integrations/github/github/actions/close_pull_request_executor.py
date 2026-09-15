import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import PullRequestActionError
from github.helpers.exceptions import InvalidActionParametersException


class ClosePullRequestExecutor(AbstractGithubExecutor):
    ACTION_NAME = "close_pull_request"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        pr_number = run.execution_properties.get("prNumber")

        if not (org and repo and pr_number):
            raise InvalidActionParametersException(
                "org, repo, and prNumber are required"
            )

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Closing pull request #{pr_number} in {org}/{repo}",
            should_raise=False,
        )

        try:
            pr = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/pulls/{pr_number}",
                method="PATCH",
                json_data={"state": "closed"},
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise PullRequestActionError.from_response(
                e.response, f"Could not close pull request #{pr_number} in {org}/{repo}"
            )
        except Exception as e:
            raise PullRequestActionError(
                f"Could not close pull request #{pr_number} in {org}/{repo}: {e}"
            )

        logger.info(
            f"Closed pull request #{pr['number']} in {org}/{repo}",
            pr_number=pr["number"],
            html_url=pr["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Pull request #{pr['number']} closed: {pr['html_url']}",
        )
