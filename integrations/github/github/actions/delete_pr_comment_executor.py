import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import PullRequestCommentError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException


class DeletePrCommentExecutor(AbstractGithubExecutor):
    ACTION_NAME = "delete_pr_comment"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return None

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        comment_id = run.execution_properties.get("commentId")

        if not (org and repo and comment_id):
            raise InvalidActionParametersException(
                "org, repo, and commentId are required"
            )

        rest_client = (await self._get_execution_clients(run))[0]
        if not isinstance(rest_client, GithubRestClient):
            raise InvalidActionParametersException("GitHub REST client is required")

        await ocean.port_client.post_run_log(
            run,
            f"Deleting comment {comment_id} in {org}/{repo}",
            should_raise=False,
        )

        try:
            response = await rest_client.make_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/issues/comments/{comment_id}",
                method="DELETE",
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise PullRequestCommentError.from_response(
                e.response,
                f"Could not delete comment {comment_id} in {org}/{repo}",
            )

        if response.status_code != 204:
            logger.warning(
                f"Unexpected status code {response.status_code} when deleting comment {comment_id} in {org}/{repo}",
                org=org,
                repo=repo,
                comment_id=comment_id,
                status_code=response.status_code,
            )
            raise PullRequestCommentError(
                f"Failed to delete comment: unexpected status code {response.status_code}"
            )

        logger.info(
            f"Deleted comment {comment_id} in {org}/{repo}",
            comment_id=comment_id,
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Comment {comment_id} deleted from {org}/{repo}",
        )
