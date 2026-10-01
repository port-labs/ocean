import httpx
from loguru import logger

from github.actions.abstract_pr_comment_executor import (
    AbstractPrCommentExecutor,
    PrCommentInputs,
)
from github.actions.exceptions import DeleteCommentError
from github.clients.http.rest_client import GithubRestClient


class DeletePrCommentInputs(PrCommentInputs):
    commentId: int


class DeletePrCommentExecutor(AbstractPrCommentExecutor[DeletePrCommentInputs]):
    ACTION_NAME = "delete_pr_comment"
    INPUTS_CLASS = DeletePrCommentInputs
    ERROR_CLASS = DeleteCommentError
    IN_PROGRESS_STATUS_LABEL = "Deleting comment"
    COMPLETED_STATUS_LABEL = "Comment deleted"

    def _start_message(self, inputs: DeletePrCommentInputs) -> str:
        return f"Deleting comment {inputs.commentId} in {inputs.repo_path}"

    async def _perform(
        self, rest_client: GithubRestClient, inputs: DeletePrCommentInputs
    ) -> str:
        # make_request, not send_api_request: DELETE returns 204 with no JSON body.
        try:
            await rest_client.make_request(
                f"{self._repo_url(rest_client, inputs)}/issues/comments/{inputs.commentId}",
                method="DELETE",
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise DeleteCommentError.from_response(
                e.response,
                f"Could not delete comment {inputs.commentId} in {inputs.repo_path}",
            )

        logger.info(
            f"Deleted comment {inputs.commentId} in {inputs.repo_path}",
            comment_id=inputs.commentId,
        )
        return f"Comment {inputs.commentId} deleted from {inputs.repo_path}"
