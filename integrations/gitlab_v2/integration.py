from typing import List, Literal, Union

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field


class GitlabProjectSelector(Selector):
    only_grouped: bool = Field(
        default=True, description="Retrieve only grouped projects", alias="onlyGrouped"
    )
    enrich_languages: bool = Field(
        default=True, description="Retrieve only grouped projects", alias="enrichLanguages"
    ),


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
