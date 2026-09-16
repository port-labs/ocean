from typing import Annotated

from pydantic import BaseModel, Field

NonEmptyStr = Annotated[str, Field(min_length=1)]


class _IssueMutationPayload(BaseModel):
    priority: int | None = None


class IssueCreateMutationPayload(_IssueMutationPayload):
    teamId: str
    title: str
    parentId: str | None = None
    description: str | None = None
    assigneeId: str | None = None
    stateId: str | None = None
    projectId: str | None = None
    cycleId: str | None = None
    labelIds: list[str] | None = None


class IssueUpdateMutationPayload(_IssueMutationPayload):
    title: str | None = None
    description: str | None = None
    assigneeId: str | None = None
    stateId: str | None = None
    projectId: str | None = None
    cycleId: str | None = None
    delegateId: str | None = None
    labelIds: list[str] | None = None


class _IssueState(BaseModel):
    id: NonEmptyStr
    name: NonEmptyStr


class MutationIssue(BaseModel):
    id: NonEmptyStr
    identifier: NonEmptyStr
    url: NonEmptyStr
    title: str | None = None
    state: _IssueState | None = None


class MutationIssueResult(BaseModel):
    success: bool
    issue: MutationIssue


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
