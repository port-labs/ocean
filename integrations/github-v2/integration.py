from github.utils import RepositoryType, PullRequestState

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


class GithubPullRequestSelector(Selector):
    state: PullRequestState = Field(
        default=PullRequestState.OPEN,
        description="Filter by pull request state (e.g., open, closed, all)",
    )


class GithubPullRequestConfig(ResourceConfig):
    selector: GithubPullRequestSelector
    kind: Literal["pull-request"]


class GithubPortAppConfig(PortAppConfig):
    resources: list[GithubRepositoryConfig | GithubPullRequestConfig | ResourceConfig]


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
