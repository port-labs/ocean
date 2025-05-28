from typing import Literal
from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

from github.helpers.utils import RepositoryType


class GithubWorkflowSelector(Selector):
    repo_type: RepositoryType = Field(
        default=RepositoryType.ALL,
        description="Filter by repository relationship (e.g., private, public)",
    )


class GithubWorkflowConfig(ResourceConfig):
    selector: GithubWorkflowSelector
    kind: Literal["workflow"]


class GithubWorkflowRunConfig(ResourceConfig):
    selector: GithubWorkflowSelector
    kind: Literal["workflow-run"]


class GithubPortAppConfig(PortAppConfig):
    repository_visibility_filter: str = Field(
        alias="repositoryVisibilityFilter", default="all"
    )
    resources: list[
        GithubRepositoryConfig
        | GithubWorkflowConfig
        | GithubWorkflowRunConfig
        | ResourceConfig
    ]


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
