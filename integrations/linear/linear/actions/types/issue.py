from typing import Annotated, Generic

from pydantic import ConfigDict, Field

from linear.actions.types.base import LinearActionPayload, MutationPayloadT, NonEmptyStr
from linear.core.mutations.issue.types import (
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
        return self.MUTATION_PAYLOAD_TYPE(**data)


class CreateIssuePayload(IssueActionPayload[IssueCreateMutationPayload]):
    MUTATION_PAYLOAD_TYPE = IssueCreateMutationPayload

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
    MUTATION_PAYLOAD_TYPE = IssueCreateMutationPayload

    parentId: NonEmptyStr
    title: NonEmptyStr
    teamId: NonEmptyStr | None = None
    description: NonEmptyStr | None = None
    assigneeId: NonEmptyStr | None = None
    stateId: NonEmptyStr | None = None
    priority: PriorityField = None


class UpdateIssuePayload(IssueActionPayload[IssueUpdateMutationPayload]):
    MUTATION_PAYLOAD_TYPE = IssueUpdateMutationPayload
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
