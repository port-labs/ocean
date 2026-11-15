from typing import Any, Self

from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class AbstractFoundryActionInput(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    projectEndpoint: str = Field(min_length=1)

    @field_validator("projectEndpoint")
    @classmethod
    def _normalize_project_endpoint(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @classmethod
    def from_execution_properties(cls, execution_properties: dict[str, Any]) -> Self:
        try:
            return cls.model_validate(execution_properties)
        except ValidationError as error:
            raise ActionExecutionError(str(error)) from error
