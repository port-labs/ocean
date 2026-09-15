from linear.actions.types.base import LinearActionPayload, NonEmptyStr
from linear.core.mutations.comment.types import CommentCreateMutationPayload


class AddCommentPayload(LinearActionPayload[CommentCreateMutationPayload]):
    MUTATION_PAYLOAD_TYPE = CommentCreateMutationPayload

    issueId: NonEmptyStr
    body: NonEmptyStr
