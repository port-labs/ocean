from typing import Annotated

from pydantic import BaseModel, Field

NonEmptyStr = Annotated[str, Field(min_length=1)]


class CommentCreateMutationPayload(BaseModel):
    issueId: str
    body: str


class MutationComment(BaseModel):
    id: NonEmptyStr
    body: NonEmptyStr
    createdAt: NonEmptyStr


class MutationCommentResult(BaseModel):
    success: bool
    comment: MutationComment
