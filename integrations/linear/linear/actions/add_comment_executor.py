from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.types import AddCommentPayload
from linear.core.mutations import CommentMutations


class AddCommentExecutor(AbstractLinearExecutor):
    ACTION_NAME = "add_comment"

    async def execute(self, run: IntegrationRun) -> None:
        payload = AddCommentPayload.from_execution_properties(run.execution_properties)

        await ocean.port_client.post_run_log(
            run,
            f"Adding comment to issue {payload.issueId}",
            status_label="Adding comment",
            should_raise=False,
        )

        mutations = CommentMutations(self.client)
        comment = await mutations.create_comment(payload.to_mutation())

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
