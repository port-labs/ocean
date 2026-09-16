from pydantic import ValidationError

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations.reaction import queries
from linear.core.mutations.reaction.types import (
    MutationReaction,
    MutationReactionResult,
    ReactionCreateMutationPayload,
)
from linear.actions.exceptions import LinearActionError


class ReactionMutations(LinearExporter):
    object_type = LinearObject.ISSUES

    async def create_reaction(
        self, payload: ReactionCreateMutationPayload
    ) -> MutationReaction:
        result = await self.graphql.execute_mutation(
            queries.REACTION_CREATE,
            {"input": payload.model_dump(exclude_none=True)},
            result_key="reactionCreate",
        )
        try:
            return MutationReactionResult.model_validate(result).reaction
        except ValidationError as validation_error:
            raise LinearActionError(
                f"Could not add reaction to issue '{payload.issueId}': Linear returned an empty or incomplete response"
            ) from validation_error
