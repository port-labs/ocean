from typing import Any, Literal
from pydantic import Field

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class ProjectSelector(Selector):
    include_labels: bool = Field(
        alias="includeLabels",
        default=False,
        description="Whether to include the labels of the project, defaults to false",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal["project"]
    selector: ProjectSelector


class GitlabPortAppConfig(PortAppConfig):
    resources: list[ProjectResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class GitlabIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitlabPortAppConfig
