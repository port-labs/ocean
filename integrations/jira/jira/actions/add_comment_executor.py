from typing import Any

import httpx
from loguru import logger
from pydantic import Field, ValidationError
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from jira.actions.abstract_jira_action_input import AbstractJiraActionInput
from jira.actions.abstract_jira_executor import AbstractJiraExecutor
from jira.actions.exceptions import AddCommentError
from jira.actions.utils import plain_text_adf


class AddCommentInput(AbstractJiraActionInput):
    issue_key: str = Field(..., alias="issueKey", min_length=1)
    comment: str = Field(..., min_length=1)

    def to_api_payload(self) -> dict[str, Any]:
        return {"body": plain_text_adf(self.comment)}


class AddCommentExecutor(AbstractJiraExecutor):
    ACTION_NAME = "add_comment"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: IntegrationRun) -> None:
        action_input = AddCommentInput.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Adding comment to Jira issue {action_input.issue_key}",
            status_label="Adding comment",
            should_raise=False,
        )

        try:
            created_comment = await self.client.add_comment(
                action_input.issue_key,
                action_input.to_api_payload(),
            )
        except httpx.HTTPStatusError as error:
            raise AddCommentError.from_response(
                error.response,
                f"Could not add comment to issue '{action_input.issue_key}'",
            )
        except ValidationError as error:
            raise AddCommentError(
                "Failed to add comment: Jira returned an empty or incomplete response"
            ) from error

        logger.info(
            "Added Jira comment",
            issue_key=action_input.issue_key,
            comment_id=created_comment.id,
        )

        await self._complete_issue_action(
            run,
            issue_key=action_input.issue_key,
            message=f"Added comment to {action_input.issue_key}",
            status_label="Comment added",
            output={"commentId": created_comment.id},
        )
