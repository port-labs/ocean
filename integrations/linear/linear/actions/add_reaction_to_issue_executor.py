from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.utils import require_property
from linear.core.mutations import ReactionMutations


class AddReactionToIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "add_reaction_to_issue"

    async def execute(self, run: IntegrationRun) -> None:
        issue_id = require_property(run, "issueId")
        emoji = require_property(run, "emoji")

        await ocean.port_client.post_run_log(
            run,
            f"Adding reaction '{emoji}' to issue {issue_id}",
            should_raise=False,
        )

        mutations = ReactionMutations(self.client)
        reaction = await mutations.create_reaction(issue_id, str(emoji))

        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Added reaction {reaction['emoji']} to issue {issue_id}",
        )
        logger.info(
            "Added Linear issue reaction",
            issue_id=issue_id,
            reaction_id=reaction["id"],
        )
