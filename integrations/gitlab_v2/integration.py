from typing import List, Literal, Union
from pydantic import Field
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class GitlabProjectSelector(Selector):
    onlyGrouped: bool = Field(default=True, description="Retrieve only grouped projects")

class GitlabProjectResourceConfig(ResourceConfig):
    kind: Literal["project"]
    selector: GitlabProjectSelector

class GitlabPortAppConfig(PortAppConfig):
    resources: List[Union[GitlabProjectResourceConfig, ResourceConfig]] = Field(
        default_factory=list
    )

class GitlabIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitlabPortAppConfig
