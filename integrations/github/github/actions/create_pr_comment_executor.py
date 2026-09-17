from typing import Any

import httpx
from loguru import logger
from pydantic import Field

from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.actions.exceptions import CreateCommentError


class CreatePrCommentInputs(AbstractGithubActionInput):
    org: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    prNumber: int
    body: str = Field(min_length=1)

    def to_api_payload(self) -> dict[str, Any]:
        return {"body": self.body}


class CreatePrCommentExecutor(AbstractGithubExecutor):
    ACTION_NAME = "create_pr_comment"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreatePrCommentInputs.from_execution_properties(
            run.execution_properties
        )

        rest_client = await self._get_rest_client(run)

        await ocean.port_client.post_run_log(
            run,
            f"Creating comment on pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo}",
            status_label="Creating comment",
            should_raise=False,
        )

        try:
            comment = await rest_client.send_api_request(
                f"{rest_client.base_url}/repos/{inputs.org}/{inputs.repo}/issues/{inputs.prNumber}/comments",
                method="POST",
                json_data=inputs.to_api_payload(),
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            raise CreateCommentError.from_response(
                e.response,
                f"Could not create comment on pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo}",
            )

        comment_id = comment.get("id")
        html_url = comment.get("html_url")
        if comment_id is None or html_url is None:
            raise CreateCommentError(
                "Failed to create comment: GitHub returned an empty or incomplete response"
            )

        message = f"Comment created on pull request #{inputs.prNumber}: {html_url}"
        logger.info(
            f"Created comment {comment_id} on pull request #{inputs.prNumber} in {inputs.org}/{inputs.repo}",
            comment_id=comment_id,
            html_url=html_url,
        )

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Comment created",
        )
