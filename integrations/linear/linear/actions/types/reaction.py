from linear.actions.types.base import LinearActionPayload, NonEmptyStr
from linear.core.mutations.reaction_mutation_payload import (
    ReactionCreateMutationPayload,
)


class AddReactionPayload(LinearActionPayload[ReactionCreateMutationPayload]):
    MUTATION_PAYLOAD_TYPE = ReactionCreateMutationPayload

    issueId: NonEmptyStr
    emoji: NonEmptyStr
