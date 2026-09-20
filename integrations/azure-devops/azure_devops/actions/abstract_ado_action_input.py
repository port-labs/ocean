from typing import Any, Self

from pydantic import BaseModel, ConfigDict, ValidationError

from azure_devops.actions.exceptions import InvalidActionParametersError


class AbstractAzureDevopsActionInput(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    @classmethod
    def from_execution_properties(cls, execution_properties: dict[str, Any]) -> Self:
        try:
            return cls.model_validate(execution_properties)
        except ValidationError as error:
            raise InvalidActionParametersError(
                cls._format_validation_error(error)
            ) from error

    @staticmethod
    def _format_validation_error(error: ValidationError) -> str:
        messages = [
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
            for err in error.errors()
        ]
        return "; ".join(messages)
