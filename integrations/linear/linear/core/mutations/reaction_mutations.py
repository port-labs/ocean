from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations import queries
from linear.core.mutations.reaction_mutation_payload import (
    ReactionCreateMutationPayload,
)
from linear.helpers.exceptions import LinearActionError


class ReactionMutations(LinearExporter):
    object_type = LinearObject.ISSUES

    async def create_reaction(
        self, payload: ReactionCreateMutationPayload
    ) -> dict[str, object]:
        result = await self.graphql.execute_mutation(
            queries.REACTION_CREATE,
            {"input": payload.model_dump(exclude_none=True)},
            result_key="reactionCreate",
        )
        reaction = result.get("reaction")
        if not isinstance(reaction, dict) or not reaction.get("id"):
            raise LinearActionError(
                f"Could not add reaction to issue '{payload.issueId}': Linear returned an empty or incomplete response"
            )
        return reaction
