from typing import Any, Self

from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from azure_integration.foundry.core.exporters.project_exporter import (
    foundry_project_from_arm_id,
)


class _FoundryInputBase(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    @classmethod
    def from_execution_properties(cls, execution_properties: dict[str, Any]) -> Self:
        try:
            return cls.model_validate(execution_properties)
        except ValidationError as error:
            raise ActionExecutionError(str(error)) from error


class AbstractFoundryActionInput(_FoundryInputBase):
    projectEndpoint: str = Field(min_length=1)

    @field_validator("projectEndpoint")
    @classmethod
    def _normalize_project_endpoint(cls, value: str) -> str:
        return value.strip().rstrip("/")


class AbstractFoundryInvokeInput(_FoundryInputBase):
    """Invoke actions take a project ARM id; data-plane URL is derived locally."""

    projectArmId: str = Field(min_length=1)

    @field_validator("projectArmId")
    @classmethod
    def _normalize_project_arm_id(cls, value: str) -> str:
        return value.strip()

    @property
    def project_endpoint(self) -> str:
        project = foundry_project_from_arm_id(self.projectArmId)
        if project is None:
            raise ActionExecutionError(
                f"Invalid Foundry projectArmId: {self.projectArmId}"
            )
        return project.endpoint.rstrip("/")
