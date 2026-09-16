from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.types import AddIssueCommentPayload
from linear.core.mutations import IssueMutations
from linear.actions.exceptions import LinearActionError


class AddIssueCommentExecutor(AbstractLinearExecutor):
    ACTION_NAME = "add_issue_comment"

    async def execute(self, run: IntegrationRun) -> None:
        payload = AddIssueCommentPayload.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Adding comment to issue {payload.issueId}",
            status_label="Adding comment",
            should_raise=False,
        )

        mutations = IssueMutations(self.client)
        try:
            comment = await mutations.create_comment(payload.to_mutation())
        except Exception as error:
            raise LinearActionError(str(error), status_label="Comment failed") from error

        logger.info(
            "Added Linear issue comment",
            issue_id=payload.issueId,
            comment_id=comment.id,
        )
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Added comment {comment.id} to issue {payload.issueId}",
            status_label="Comment added",
        )
