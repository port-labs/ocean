from abc import ABC
from typing import Any, ClassVar, Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from linear.core.mutations.types import NonEmptyStr
from linear.actions.exceptions import MissingExecutionPropertyError

MutationPayloadT = TypeVar("MutationPayloadT", bound=BaseModel)


class LinearActionPayload(BaseModel, Generic[MutationPayloadT], ABC):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    payload_exclude: ClassVar[set[str]] = set()
    MUTATION_PAYLOAD_TYPE: ClassVar[type[MutationPayloadT]]

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(
            exclude=self.payload_exclude,
            exclude_none=True,
        )

    def to_mutation(self) -> MutationPayloadT:
        return self.MUTATION_PAYLOAD_TYPE(**self.to_payload())

    @classmethod
    def from_execution_properties(cls, execution_properties: dict[str, Any]) -> Self:
        try:
            return cls.model_validate(execution_properties)
        except ValidationError as error:
            raise MissingExecutionPropertyError(str(error)) from error
