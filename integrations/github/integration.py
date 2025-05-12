from github.utils import RepositoryType

from typing import Literal
from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration


class GithubRepositorySelector(Selector):
    type: RepositoryType = Field(
        default=RepositoryType.ALL,
        description="Filter by repository relationship (e.g., private, public)",
    )


class GithubRepositoryConfig(ResourceConfig):
    selector: GithubRepositorySelector
    kind: Literal["repository"]


class GithubPortAppConfig(PortAppConfig):
    resources: list[GithubRepositoryConfig | ResourceConfig]


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
