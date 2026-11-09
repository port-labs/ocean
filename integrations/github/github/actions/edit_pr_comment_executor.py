from loguru import logger
from pydantic import Field

from github.actions.abstract_pr_comment_executor import (
    AbstractPrCommentExecutor,
    PrCommentInputs,
)
from github.actions.exceptions import EditCommentError
from github.clients.http.rest_client import GithubRestClient


class EditPrCommentInputs(PrCommentInputs):
    commentId: int
    body: str = Field(min_length=1)


class EditPrCommentExecutor(AbstractPrCommentExecutor[EditPrCommentInputs]):
    ACTION_NAME = "edit_pr_comment"
    INPUTS_CLASS = EditPrCommentInputs
    ERROR_CLASS = EditCommentError
    IN_PROGRESS_STATUS_LABEL = "Editing comment"
    COMPLETED_STATUS_LABEL = "Comment updated"

    def _start_message(self, inputs: EditPrCommentInputs) -> str:
        return f"Editing comment {inputs.commentId} in {inputs.repo_path}"

    async def _perform(
        self, rest_client: GithubRestClient, inputs: EditPrCommentInputs
    ) -> str:
        comment_id, html_url = await self._write_comment(
            rest_client,
            f"{self._repo_url(rest_client, inputs)}/issues/comments/{inputs.commentId}",
            method="PATCH",
            body=inputs.body,
            error_prefix=f"Could not edit comment {inputs.commentId} in {inputs.repo_path}",
        )

        logger.info(
            f"Edited comment {comment_id} in {inputs.repo_path}",
            comment_id=comment_id,
            html_url=html_url,
        )
        return f"Comment updated: {html_url}"
