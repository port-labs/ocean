from typing import Any, Self

from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class InvalidActionParametersException(ActionExecutionError):
    """Raised when action execution properties fail validation."""


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
            raise InvalidActionParametersException(
                cls._format_validation_error(error)
            ) from error

    @staticmethod
    def _format_validation_error(error: ValidationError) -> str:
        messages = [
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
            for err in error.errors()
        ]
        return "; ".join(messages)
