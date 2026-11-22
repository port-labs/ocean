from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScenarioExpect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: str | None = None
    unmatched_requests: Literal["none"] | None = None
    resync_status: str | None = None


class ScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    kinds: list[str] = Field(default_factory=list)
    routes: list[str] = Field(min_length=1)
    blueprints: str | None = None
    port_app_config_overrides: list[dict[str, Any]] | None = None
    expect: ScenarioExpect | None = None


class ScenariosDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    integration_config: dict[str, Any] = Field(default_factory=dict)
    port_app_config: str = Field(..., min_length=1)
    blueprints: str = Field(default=".port/resources/blueprints.json", min_length=1)
    ignore_fields: list[str] = Field(default_factory=list)


class ScenariosDocument(BaseModel):
    """Typed view of ``<integration>/validation/scenarios.yaml``."""

    model_config = ConfigDict(extra="forbid")

    defaults: ScenariosDefaults
    scenarios: dict[str, ScenarioDefinition] = Field(min_length=1)

    @field_validator("scenarios")
    @classmethod
    def _scenario_names_must_be_non_empty(
        cls, value: dict[str, ScenarioDefinition]
    ) -> dict[str, ScenarioDefinition]:
        for name in value:
            if not name.strip():
                raise ValueError("scenario names must be non-empty strings")
        return value


class ValidationPaths(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_root: Path
    validation_root: Path
    scenarios_file: Path
    mock_root: Path

    @property
    def integration_name(self) -> str:
        return self.integration_root.name
