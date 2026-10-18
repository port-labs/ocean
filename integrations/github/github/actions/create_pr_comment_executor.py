from loguru import logger
from pydantic import Field

from github.actions.abstract_pr_comment_executor import (
    AbstractPrCommentExecutor,
    PrCommentInputs,
)
from github.actions.exceptions import CreateCommentError
from github.clients.http.rest_client import GithubRestClient


class CreatePrCommentInputs(PrCommentInputs):
    prNumber: int
    body: str = Field(min_length=1)


class CreatePrCommentExecutor(AbstractPrCommentExecutor[CreatePrCommentInputs]):
    ACTION_NAME = "create_pr_comment"
    INPUTS_CLASS = CreatePrCommentInputs
    ERROR_CLASS = CreateCommentError
    IN_PROGRESS_STATUS_LABEL = "Creating comment"
    COMPLETED_STATUS_LABEL = "Comment created"

    def _start_message(self, inputs: CreatePrCommentInputs) -> str:
        return (
            f"Creating comment on pull request #{inputs.prNumber} in {inputs.repo_path}"
        )

    async def _perform(
        self, rest_client: GithubRestClient, inputs: CreatePrCommentInputs
    ) -> str:
        comment_id, html_url = await self._write_comment(
            rest_client,
            f"{self._repo_url(rest_client, inputs)}/issues/{inputs.prNumber}/comments",
            method="POST",
            body=inputs.body,
            error_prefix=f"Could not create comment on pull request #{inputs.prNumber} in {inputs.repo_path}",
        )

        logger.info(
            f"Created comment {comment_id} on pull request #{inputs.prNumber} in {inputs.repo_path}",
            comment_id=comment_id,
            html_url=html_url,
        )
        return f"Comment created on pull request #{inputs.prNumber}: {html_url}"
