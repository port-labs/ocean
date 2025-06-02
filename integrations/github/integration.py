from typing import Literal, Optional
from datetime import datetime
from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration


class GithubPullRequestSelector(Selector):
    state: Literal["open", "closed", "all"] = Field(
        default="open",
        description="Filter by pull request state (e.g., open, closed, all)",
    )
    start_time: Optional[datetime] = Field(
        alias="startTime",
        default=None,
        description="Filter pull requests created after this time (ISO format)",
    )
    end_time: Optional[datetime] = Field(
        alias="endTime",
        default=None,
        description="Filter pull requests created before this time (ISO format)",
    )


class GithubPullRequestConfig(ResourceConfig):
    selector: GithubPullRequestSelector
    kind: Literal["pull-request"]


class GithubPortAppConfig(PortAppConfig):
    repository_type: str = Field(alias="repositoryType", default="all")
    resources: list[GithubPullRequestConfig | ResourceConfig]


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
