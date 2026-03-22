from typing import Literal

import pytest

from pydantic import Field
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)


class ObjectKind:
    REPOSITORY = "repositories"
    ISSUES = "issues"
    ISSUE_GROUPS = "issue_groups"
    TEAM = "team"
    CONTAINER = "containers"


class RepositorySelector(Selector):
    include_inactive: bool = Field(
        default=False,
        alias="includeInactive",
        title="Include Inactive",
        description="Whether to include inactive repositories",
    )


class RepositoryResourceConfig(ResourceConfig):
    kind: Literal["repositories"] = Field(
        title="Aikido Repository",
        description="Aikido repository resource kind.",
    )
    selector: RepositorySelector = Field(
        title="Repository Selector",
        description="Selector for the Aikido repository resource.",
    )


class ContainerSelector(Selector):
    filter_status: Literal["all", "active", "inactive"] = Field(
        default="active",
        alias="filterStatus",
        title="Filter Status",
        description="Filter containers by status: all, active, or inactive",
    )


class ContainerResourceConfig(ResourceConfig):
    kind: Literal["containers"] = Field(
        title="Aikido Container",
        description="Aikido container resource kind.",
    )
    selector: ContainerSelector = Field(
        title="Container Selector",
        description="Selector for the Aikido container resource.",
    )


class IssueResourceConfig(ResourceConfig):
    kind: Literal["issues"] = Field(
        title="Aikido Issue",
        description="Aikido issue resource kind.",
    )


class IssueGroupResourceConfig(ResourceConfig):
    kind: Literal["issue_groups"] = Field(
        title="Aikido Issue Group",
        description="Aikido issue group resource kind.",
    )


class TeamResourceConfig(ResourceConfig):
    kind: Literal["team"] = Field(
        title="Aikido Team",
        description="Aikido team resource kind.",
    )


class AikidoPortAppConfig(PortAppConfig):
    resources: list[
        RepositoryResourceConfig
        | ContainerResourceConfig
        | IssueResourceConfig
        | IssueGroupResourceConfig
        | TeamResourceConfig
    ] = Field(
        default_factory=list,
        title="Resources",
        description="Resources configuration for this Port app.",
    )  # type: ignore[assignment]


class AikidoIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AikidoPortAppConfig


def test_aikido_app_config_schema_includes_new_resource_kinds():
    """
    Ensure that the generated config schema for AikidoPortAppConfig
    includes the newly added resource kinds, to prevent regressions in
    schema extraction / UI compliance.
    """

    schema = AikidoPortAppConfig.schema()

    def _collect_enum_values(obj, enums: set[str]) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "enum" and isinstance(value, list):
                    enums.update(str(item) for item in value)
                else:
                    _collect_enum_values(value, enums)
        elif isinstance(obj, list):
            for item in obj:
                _collect_enum_values(item, enums)

    enum_values: set[str] = set()
    _collect_enum_values(schema, enum_values)

    assert "issues" in enum_values
    assert "issue_groups" in enum_values
    assert "team" in enum_values
