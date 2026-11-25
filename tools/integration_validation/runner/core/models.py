from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator


class ScenarioExpect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: str | None = None
    unmatched_requests: Literal["none"] | None = None
    resync_status: str | None = None


class PortAppConfigOverride(BaseModel):
    """Scenario overlay merged into a ``port_app_config`` resource of the same ``kind``."""

    model_config = ConfigDict(extra="allow")

    kind: str = Field(min_length=1)


class ScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    kinds: list[str] = Field(default_factory=list)
    routes: list[str] = Field(min_length=1)
    blueprints: str | None = None
    integration_config: dict[str, Any] | None = None
    port_app_config_overrides: list[PortAppConfigOverride] | None = None
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


class BlueprintDefinition(BaseModel):
    """Minimal shape of a Port blueprint entry for validation runs."""

    model_config = ConfigDict(extra="allow")

    identifier: str = Field(min_length=1)


class BlueprintsDocument(RootModel[list[BlueprintDefinition]]):
    """Typed view of an integration ``blueprints.json`` array."""

    def as_mappings(self) -> list[dict[str, Any]]:
        return self.model_dump(mode="python")


class PortEntity(BaseModel):
    """An entity as Port's search returns it, or as a snapshot file stores it."""

    model_config = ConfigDict(extra="allow", frozen=True)

    identifier: str = Field(min_length=1)
    title: str | None = None
    icon: str | None = None
    team: list[str] | str | None = None
    properties: dict[str, Any] | None = None
    relations: dict[str, Any] | None = None
    blueprint: str | None = None

    def as_json(self) -> dict[str, Any]:
        """Only the keys the payload had, so snapshots keep the shape Port returned."""
        return self.model_dump(exclude_unset=True)


# Keyed by the blueprint identifier in the integration's blueprints file.
EntitiesByBlueprint = dict[str, list[PortEntity]]


class PortAppConfigResource(BaseModel):
    """Minimal shape of a ``port_app_config`` resource entry for validation runs."""

    model_config = ConfigDict(extra="allow")

    kind: str = Field(min_length=1)
    port: dict[str, Any] = Field(default_factory=dict)


class PortAppConfigDocument(BaseModel):
    """Typed view of an integration ``port-app-config.yaml`` (validation subset)."""

    model_config = ConfigDict(extra="allow")

    resources: list[PortAppConfigResource]

    def as_mapping(self) -> dict[str, Any]:
        return self.model_dump(mode="python")


class ValidationPaths(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_root: Path
    validation_root: Path
    scenarios_file: Path
    mock_root: Path

    @property
    def integration_name(self) -> str:
        return self.integration_root.name
