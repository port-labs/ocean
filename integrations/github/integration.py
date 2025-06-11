from typing import Literal
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

class GithubPullRequestConfig(ResourceConfig):
    selector: GithubPullRequestSelector
    kind: Literal["pull-request"]


class GithubIssueSelector(Selector):
    state: Literal["open", "closed", "all"] = Field(
        default="open",
        description="Filter by issue state (open, closed, all)",
    )

class GithubIssueConfig(ResourceConfig):
    selector: GithubIssueSelector
    kind: Literal["issue"]
    

class GithubPortAppConfig(PortAppConfig):
    repository_type: str = Field(alias="repositoryType", default="all")
    resources: list[GithubPullRequestConfig | GithubIssueConfig | ResourceConfig]


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
