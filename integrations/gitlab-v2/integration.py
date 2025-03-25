from typing import Literal

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field


class ProjectSelector(Selector):
    include_languages: bool = Field(
        alias="includeLanguages",
        default=False,
        description="Whether to include the languages of the project, defaults to false",
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
