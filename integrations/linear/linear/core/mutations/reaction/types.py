from typing import Annotated

from pydantic import BaseModel, Field

NonEmptyStr = Annotated[str, Field(min_length=1)]


class ReactionCreateMutationPayload(BaseModel):
    issueId: str
    emoji: str


class MutationReaction(BaseModel):
    id: NonEmptyStr
    emoji: NonEmptyStr


class MutationReactionResult(BaseModel):
    success: bool
    reaction: MutationReaction
