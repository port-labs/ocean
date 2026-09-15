from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations import queries
from linear.core.mutations.comment_mutation_payload import CommentCreateMutationPayload
from linear.helpers.exceptions import LinearActionError


class CommentMutations(LinearExporter):
    object_type = LinearObject.ISSUES

    async def create_comment(
        self, payload: CommentCreateMutationPayload
    ) -> dict[str, object]:
        result = await self.graphql.execute_mutation(
            queries.COMMENT_CREATE,
            {"input": payload.model_dump(exclude_none=True)},
            result_key="commentCreate",
        )
        comment = result.get("comment")
        if not isinstance(comment, dict) or not comment.get("id"):
            raise LinearActionError(
                f"Could not add comment to issue '{payload.issueId}': Linear returned an empty or incomplete response"
            )
        return comment
