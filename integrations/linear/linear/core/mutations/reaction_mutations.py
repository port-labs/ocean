from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations import queries
from linear.helpers.exceptions import LinearActionError


class ReactionMutations(LinearExporter):
    object_type = LinearObject.ISSUES

    async def create_reaction(self, issue_id: str, emoji: str) -> dict[str, object]:
        result = await self.graphql.execute_mutation(
            queries.REACTION_CREATE,
            {"input": {"issueId": issue_id, "emoji": emoji}},
            result_key="reactionCreate",
        )
        reaction = result.get("reaction")
        if not isinstance(reaction, dict) or not reaction.get("id"):
            raise LinearActionError(
                f"Could not add reaction to issue '{issue_id}': Linear returned an empty or incomplete response"
            )
        return reaction
