import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import PullRequestCommentError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException


class CreatePrCommentExecutor(AbstractGithubExecutor):
    ACTION_NAME = "create_pr_comment"
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
        pr_number = run.execution_properties.get("prNumber")
        body = run.execution_properties.get("body")

        if not (org and repo and pr_number and body):
            raise InvalidActionParametersException(
                "org, repo, prNumber, and body are required"
            )

        rest_client = (await self._get_execution_clients(run))[0]
        if not isinstance(rest_client, GithubRestClient):
            raise InvalidActionParametersException("GitHub REST client is required")

        await ocean.port_client.post_run_log(
            run,
            f"Creating comment on pull request #{pr_number} in {org}/{repo}",
            should_raise=False,
        )

        try:
            comment = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/issues/{pr_number}/comments",
                method="POST",
                json_data={"body": body},
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise PullRequestCommentError.from_response(
                e.response,
                f"Could not create comment on pull request #{pr_number} in {org}/{repo}",
            )

        if not comment or "id" not in comment or "html_url" not in comment:
            logger.warning(
                f"Received empty or incomplete response from GitHub for comment creation on pull request #{pr_number} in {org}/{repo}",
                org=org,
                repo=repo,
                pr_number=pr_number,
            )
            raise PullRequestCommentError(
                "Failed to create comment: upstream returned an empty or incomplete response"
            )

        logger.info(
            f"Created comment {comment['id']} on pull request #{pr_number} in {org}/{repo}",
            comment_id=comment["id"],
            html_url=comment["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Comment created on pull request #{pr_number}: {comment['html_url']}",
        )
