from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import require_property
from linear.core.mutations import CommentMutations


class AddCommentExecutor(AbstractLinearExecutor):
    ACTION_NAME = "add_comment"

    async def execute(self, run: IntegrationRun) -> None:
        issue_id = require_property(run, "issueId")
        body = require_property(run, "body")

        await ocean.port_client.post_run_log(
            run,
            f"Adding comment to issue {issue_id}",
            should_raise=False,
        )

        mutations = CommentMutations(self.client)
        comment = await mutations.create_comment(issue_id, str(body))

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Added comment {comment['id']} to issue {issue_id}",
        )
        logger.info(
            "Added Linear issue comment",
            issue_id=issue_id,
            comment_id=comment["id"],
        )
