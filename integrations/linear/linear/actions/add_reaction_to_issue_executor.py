from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.actions.types import AddReactionPayload
from linear.core.mutations import ReactionMutations


class AddReactionToIssueExecutor(AbstractLinearExecutor):
    ACTION_NAME = "add_reaction_to_issue"

    async def execute(self, run: IntegrationRun) -> None:
        payload = AddReactionPayload.from_execution_properties(run.execution_properties)

        await ocean.port_client.post_run_log(
            run,
            f"Adding reaction '{payload.emoji}' to issue {payload.issueId}",
            status_label="Adding reaction",
            should_raise=False,
        )

        mutations = ReactionMutations(self.client)
        reaction = await mutations.create_reaction(payload.to_mutation())

        logger.info(
            "Added Linear issue reaction",
            issue_id=payload.issueId,
            reaction_id=reaction["id"],
        )
        await ocean.port_client.report_run_completed(
            run,
            success=True,
            message=f"Added reaction {reaction['emoji']} to issue {payload.issueId}",
            status_label="Reaction added",
        )
