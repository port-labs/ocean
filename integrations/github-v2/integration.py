from github.utils import RepositoryType, IssueState
from typing import Literal, Optional, Union
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


class GithubIssueSelector(Selector):
    state: IssueState = Field(
        default=IssueState.OPEN,
        description="Filter by issue state (open, closed, all)",
    )
    labels: Optional[str] = Field(
        default=None,
        description="Filter by issue labels (comma-separated list)",
    )


class GithubIssueConfig(ResourceConfig):
    selector: GithubIssueSelector
    kind: Literal["issue"]


class GithubPortAppConfig(PortAppConfig):
    resources: list[Union[GithubRepositoryConfig, GithubIssueConfig, ResourceConfig]]


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
