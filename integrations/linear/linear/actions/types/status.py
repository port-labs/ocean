from typing import Self

from pydantic import model_validator

from linear.actions.types.base import LinearActionPayload, NonEmptyStr
from linear.core.mutations.issue.types import IssueUpdateMutationPayload
from linear.helpers.exceptions import MissingExecutionPropertyError


class ChangeStatusPayload(LinearActionPayload[IssueUpdateMutationPayload]):
    MUTATION_PAYLOAD_TYPE = IssueUpdateMutationPayload
    payload_exclude = {"issueId", "stateName"}

    issueId: NonEmptyStr
    stateId: NonEmptyStr | None = None
    stateName: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_state_input(self) -> Self:
        if not self.stateId and not self.stateName:
            raise ValueError("stateId or stateName is required")
        return self

    def to_mutation(self) -> IssueUpdateMutationPayload:
        if not self.stateId:
            raise MissingExecutionPropertyError("stateId or stateName is required")
        return IssueUpdateMutationPayload(stateId=self.stateId)
