from pydantic import ValidationError

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import LinearExporter
from linear.core.mutations.comment import queries
from linear.core.mutations.comment.types import (
    CommentCreateMutationPayload,
    MutationComment,
    MutationCommentResult,
)
from linear.helpers.exceptions import LinearActionError


class CommentMutations(LinearExporter):
    object_type = LinearObject.ISSUES

    async def create_comment(
        self, payload: CommentCreateMutationPayload
    ) -> MutationComment:
        result = await self.graphql.execute_mutation(
            queries.COMMENT_CREATE,
            {"input": payload.model_dump(exclude_none=True)},
            result_key="commentCreate",
        )
        try:
            return MutationCommentResult.model_validate(result).comment
        except ValidationError as validation_error:
            raise LinearActionError(
                f"Could not add comment to issue '{payload.issueId}': Linear returned an empty or incomplete response"
            ) from validation_error
