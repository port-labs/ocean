from typing import Annotated, Generic

from pydantic import ConfigDict, Field

from linear.actions.types.base import LinearActionPayload, MutationPayloadT, NonEmptyStr
from linear.core.mutations.issue_mutation_payload import (
    IssueCreateMutationPayload,
    IssueUpdateMutationPayload,
)
from linear.utils import PRIORITY_BY_LABEL, PriorityLabel

PriorityField = Annotated[
    PriorityLabel | None,
    Field(default=None, description=", ".join(label.value for label in PriorityLabel)),
]


class IssueActionPayload(
    LinearActionPayload[MutationPayloadT], Generic[MutationPayloadT]
):
    model_config = ConfigDict(use_enum_values=True)

    def to_mutation(self) -> MutationPayloadT:
        data = self.to_payload()
        if priority := data.get("priority"):
            priority_label = (
                priority
                if isinstance(priority, PriorityLabel)
                else PriorityLabel(priority)
            )
            data["priority"] = PRIORITY_BY_LABEL[priority_label]
        return self.mutation_payload_type()(**data)


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
    priority: PriorityField = None
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
    priority: PriorityField = None


class UpdateIssuePayload(IssueActionPayload[IssueUpdateMutationPayload]):
    @classmethod
    def mutation_payload_type(cls) -> type[IssueUpdateMutationPayload]:
        return IssueUpdateMutationPayload

    payload_exclude = {"issueId"}

    issueId: NonEmptyStr
    title: NonEmptyStr | None = None
    description: NonEmptyStr | None = None
    assigneeId: NonEmptyStr | None = None
    stateId: NonEmptyStr | None = None
    projectId: NonEmptyStr | None = None
    cycleId: NonEmptyStr | None = None
    priority: PriorityField = None
    delegateId: NonEmptyStr | None = None
    labelIds: list[str] | None = None
