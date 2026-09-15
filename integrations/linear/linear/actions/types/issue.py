from typing import Annotated, Any, Generic, Literal

from pydantic import Field

from linear.actions.types.base import LinearActionPayload, MutationPayloadT, NonEmptyStr
from linear.core.mutations.issue_mutation_payload import (
    IssueCreateMutationPayload,
    IssueUpdateMutationPayload,
)
from linear.utils import PRIORITY_BY_LABEL

PriorityLabel = Annotated[
    Literal[*PRIORITY_BY_LABEL],
    Field(description="No priority, Urgent, High, Normal, or Low"),
]


class IssueActionPayload(LinearActionPayload[MutationPayloadT], Generic[MutationPayloadT]):
    def _to_mutation_data(self) -> dict[str, Any]:
        data = self.to_payload()
        if priority := data.get("priority"):
            data["priority"] = PRIORITY_BY_LABEL[priority]
        return data


class CreateIssuePayload(IssueActionPayload[IssueCreateMutationPayload]):
    @classmethod
    def mutation_payload_type(cls) -> type[IssueCreateMutationPayload]:
        return IssueCreateMutationPayload

    teamId: NonEmptyStr
    title: NonEmptyStr
    description: NonEmptyStr | None = None
    assigneeId: NonEmptyStr | None = None
    stateId: NonEmptyStr | None = None
    projectId: NonEmptyStr | None = None
    cycleId: NonEmptyStr | None = None
    priority: PriorityLabel | None = None
    labelIds: list[str] | None = None


class CreateSubIssuePayload(IssueActionPayload[IssueCreateMutationPayload]):
    @classmethod
    def mutation_payload_type(cls) -> type[IssueCreateMutationPayload]:
        return IssueCreateMutationPayload

    parentId: NonEmptyStr
    title: NonEmptyStr
    teamId: NonEmptyStr | None = None
    description: NonEmptyStr | None = None
    assigneeId: NonEmptyStr | None = None
    stateId: NonEmptyStr | None = None
    priority: PriorityLabel | None = None


class UpdateIssuePayload(IssueActionPayload[IssueUpdateMutationPayload]):
    @classmethod
    def mutation_payload_type(cls) -> type[IssueUpdateMutationPayload]:
        return IssueUpdateMutationPayload

    payload_exclude = frozenset({"issueId"})

    issueId: NonEmptyStr
    title: NonEmptyStr | None = None
    description: NonEmptyStr | None = None
    assigneeId: NonEmptyStr | None = None
    stateId: NonEmptyStr | None = None
    projectId: NonEmptyStr | None = None
    cycleId: NonEmptyStr | None = None
    priority: PriorityLabel | None = None
    delegateId: NonEmptyStr | None = None
    labelIds: list[str] | None = None
