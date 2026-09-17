import httpx
from loguru import logger
from pydantic import Field

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import DeleteCommentError


class DeletePrCommentInputs(AbstractGithubActionInput):
    org: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    commentId: int


class DeletePrCommentExecutor(AbstractGithubExecutor):
    ACTION_NAME = "delete_pr_comment"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = DeletePrCommentInputs.from_execution_properties(
            run.execution_properties
        )

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Deleting comment {inputs.commentId} in {inputs.org}/{inputs.repo}",
            status_label="Deleting comment",
            should_raise=False,
        )

        try:
            await rest_client.make_request(
                f"{rest_client.base_url}/repos/{inputs.org}/{inputs.repo}/issues/comments/{inputs.commentId}",
                method="DELETE",
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise DeleteCommentError.from_response(
                e.response,
                f"Could not delete comment {inputs.commentId} in {inputs.org}/{inputs.repo}",
            )

        logger.info(
            f"Deleted comment {inputs.commentId} in {inputs.org}/{inputs.repo}",
            comment_id=inputs.commentId,
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Comment {inputs.commentId} deleted from {inputs.org}/{inputs.repo}",
            status_label="Comment deleted",
        )
