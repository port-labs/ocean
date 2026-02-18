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
    CONTAINER = "container"


class RepositorySelector(Selector):
    include_inactive: bool = Field(
        default=False,
        alias="includeInactive",
        description="Whether to include inactive repositories",
    )


class RepositoryResourceConfig(ResourceConfig):
    kind: Literal["repositories"]
    selector: RepositorySelector


class AikidoPortAppConfig(PortAppConfig):
    resources: list[RepositoryResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class AikidoIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AikidoPortAppConfig
