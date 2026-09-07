from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, ValidationError

from actions.exceptions import MissingExecutionPropertyError


class AbstractPagerDutyActionInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @staticmethod
    def non_empty_str(value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value

    @classmethod
    def from_execution_properties(
        cls, execution_properties: dict[str, Any]
    ) -> Self:
        try:
            return cls.model_validate(execution_properties)
        except ValidationError as error:
            raise MissingExecutionPropertyError(str(error)) from error
