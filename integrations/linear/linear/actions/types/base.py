from abc import ABC, abstractmethod
from typing import Annotated, Any, ClassVar, Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from linear.helpers.exceptions import MissingExecutionPropertyError

NonEmptyStr = Annotated[str, Field(min_length=1)]

MutationPayloadT = TypeVar("MutationPayloadT", bound=BaseModel)


class LinearActionPayload(BaseModel, Generic[MutationPayloadT], ABC):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    payload_exclude: ClassVar[frozenset[str]] = frozenset()

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(
            exclude=self.payload_exclude,
            exclude_none=True,
        )

    def _to_mutation_data(self) -> dict[str, Any]:
        return self.to_payload()

    @classmethod
    @abstractmethod
    def mutation_payload_type(cls) -> type[MutationPayloadT]: ...

    def to_mutation(self) -> MutationPayloadT:
        return self.mutation_payload_type().model_validate(self._to_mutation_data())

    @classmethod
    def from_execution_properties(cls, execution_properties: dict[str, Any]) -> Self:
        try:
            return cls.model_validate(execution_properties)
        except ValidationError as error:
            raise MissingExecutionPropertyError(str(error)) from error
