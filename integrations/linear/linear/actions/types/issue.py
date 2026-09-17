from typing import Annotated, Any, Generic, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from linear.actions.exceptions import MissingExecutionPropertyError
from linear.actions.types.base import LinearActionPayload, MutationPayloadT
from linear.types import NonEmptyStr
from linear.core.mutations.issue.types import (
    CommentCreateMutationPayload,
    IssueCreateMutationPayload,
    IssueUpdateMutationPayload,
)
from linear.core.mutations.issue.types import ReactionCreateMutationPayload
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
    labelIds: list[str] | None = None

    @model_validator(mode="after")
    def validate_at_least_one_update_field(self) -> Self:
        if not self.to_payload():
            raise ValueError(
                "At least one update field is required (title, description, assigneeId, stateId, projectId, cycleId, priority, or labelIds)"
            )
        return self


class AddIssueCommentPayload(LinearActionPayload[CommentCreateMutationPayload]):
    MUTATION_PAYLOAD_TYPE = CommentCreateMutationPayload

    issueId: NonEmptyStr
    body: NonEmptyStr


class IssueIdPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    issueId: NonEmptyStr

    @classmethod
    def from_execution_properties(cls, execution_properties: dict[str, Any]) -> Self:
        try:
            return cls.model_validate(execution_properties)
        except ValidationError as error:
            raise MissingExecutionPropertyError(str(error)) from error


class AddReactionPayload(LinearActionPayload[ReactionCreateMutationPayload]):
    MUTATION_PAYLOAD_TYPE = ReactionCreateMutationPayload

    issueId: NonEmptyStr
    emoji: NonEmptyStr


class ArchiveIssuePayload(IssueIdPayload):
    pass


class DeleteIssuePayload(IssueIdPayload):
    pass


class DelegateIssuePayload(LinearActionPayload[IssueUpdateMutationPayload]):
    MUTATION_PAYLOAD_TYPE = IssueUpdateMutationPayload
    payload_exclude = {"issueId"}

    issueId: NonEmptyStr
    delegateId: NonEmptyStr
