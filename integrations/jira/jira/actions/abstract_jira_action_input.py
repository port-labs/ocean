from typing import Any, Self

from pydantic import BaseModel, ConfigDict, ValidationError

from jira.actions.exceptions import MissingExecutionPropertyError


class AbstractJiraActionInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_execution_properties(cls, execution_properties: dict[str, Any]) -> Self:
        try:
            return cls.model_validate(execution_properties)
        except ValidationError as error:
            raise MissingExecutionPropertyError(str(error)) from error
