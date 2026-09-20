from typing import Any

import httpx
from loguru import logger
from pydantic import Field
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from jira.actions.abstract_jira_action_input import AbstractJiraActionInput
from jira.actions.abstract_jira_executor import AbstractJiraExecutor
from jira.actions.exceptions import AddCommentError
from jira.actions.utils import get_issue_browse_url, plain_text_adf


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

        comment_id = created_comment.get("id")
        if comment_id is None:
            raise AddCommentError(
                "Failed to add comment: Jira returned an empty or incomplete response"
            )

        issue_url = get_issue_browse_url(
            self.client.jira_url,
            action_input.issue_key,
            oauth_enabled=self.client.is_oauth_enabled(),
        )
        message = f"Added comment to {action_input.issue_key}"
        if issue_url:
            message = f"{message}: {issue_url}"

        await ocean.port_client.post_run_log(
            run,
            message,
            should_raise=False,
        )
        logger.info(
            "Added Jira comment",
            issue_key=action_input.issue_key,
            comment_id=comment_id,
        )

        if isinstance(run, WorkflowNodeRun):
            run.output = {
                "issueKey": action_input.issue_key,
                "commentId": str(comment_id),
                "issueUrl": issue_url or "",
            }
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=message,
            status_label="Comment added",
        )
