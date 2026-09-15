import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import PullRequestCommentError
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import InvalidActionParametersException


class EditPrCommentExecutor(AbstractGithubExecutor):
    ACTION_NAME = "edit_pr_comment"
    WEBHOOK_PROCESSOR_CLASS = None

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return None

    async def execute(self, run: IntegrationRun) -> None:
        org = run.execution_properties.get("org")
        repo = run.execution_properties.get("repo")
        comment_id = run.execution_properties.get("commentId")
        body = run.execution_properties.get("body")

        if not (org and repo and comment_id and body):
            raise InvalidActionParametersException(
                "org, repo, commentId, and body are required"
            )

        rest_client = (await self._get_execution_clients(run))[0]
        if not isinstance(rest_client, GithubRestClient):
            raise InvalidActionParametersException("GitHub REST client is required")

        await ocean.port_client.post_run_log(
            run,
            f"Editing comment {comment_id} in {org}/{repo}",
            should_raise=False,
        )

        try:
            comment = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{org}/{repo}/issues/comments/{comment_id}",
                method="PATCH",
                json_data={"body": body},
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise PullRequestCommentError.from_response(
                e.response,
                f"Could not edit comment {comment_id} in {org}/{repo}",
            )

        if not comment or "id" not in comment or "html_url" not in comment:
            logger.warning(
                f"Received empty or incomplete response from GitHub for comment edit in {org}/{repo}",
                org=org,
                repo=repo,
                comment_id=comment_id,
            )
            raise PullRequestCommentError(
                "Failed to edit comment: upstream returned an empty or incomplete response"
            )

        logger.info(
            f"Edited comment {comment['id']} in {org}/{repo}",
            comment_id=comment["id"],
            html_url=comment["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Comment updated: {comment['html_url']}",
        )
