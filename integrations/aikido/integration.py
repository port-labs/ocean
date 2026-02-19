from typing import Literal

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
        description="Whether to include inactive repositories",
    )


class RepositoryResourceConfig(ResourceConfig):
    kind: Literal["repositories"]
    selector: RepositorySelector


class ContainerSelector(Selector):
    filter_status: Literal["all", "active", "inactive"] = Field(
        default="active",
        alias="filterStatus",
        description="Filter containers by status: all, active, or inactive",
    )


class ContainerResourceConfig(ResourceConfig):
    kind: Literal["containers"]
    selector: ContainerSelector


class AikidoPortAppConfig(PortAppConfig):
    resources: list[RepositoryResourceConfig | ContainerResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class AikidoIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AikidoPortAppConfig
