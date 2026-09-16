from typing import Any

import httpx
from loguru import logger
from pydantic import Field

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import EditCommentError


class EditPrCommentInputs(AbstractGithubActionInput):
    org: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    commentId: int
    body: str = Field(min_length=1)

    def to_api_payload(self) -> dict[str, Any]:
        return {"body": self.body}


class EditPrCommentExecutor(AbstractGithubExecutor):
    ACTION_NAME = "edit_pr_comment"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = EditPrCommentInputs.from_execution_properties(run.execution_properties)

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Editing comment {inputs.commentId} in {inputs.org}/{inputs.repo}",
            status_label="Editing comment",
            should_raise=False,
        )

        try:
            comment = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{inputs.org}/{inputs.repo}/issues/comments/{inputs.commentId}",
                method="PATCH",
                json_data=inputs.to_api_payload(),
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise EditCommentError.from_response(
                e.response,
                f"Could not edit comment {inputs.commentId} in {inputs.org}/{inputs.repo}",
            )

        comment_id = comment.get("id")
        if comment_id is None:
            raise EditCommentError(
                "Failed to edit comment: GitHub returned an empty or incomplete response"
            )

        message = f"Comment updated: {comment['html_url']}"
        logger.info(
            f"Edited comment {comment_id} in {inputs.org}/{inputs.repo}",
            comment_id=comment_id,
            html_url=comment["html_url"],
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Comment updated",
        )
