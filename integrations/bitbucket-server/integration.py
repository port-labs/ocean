from enum import StrEnum
from typing import Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.fields import Field


class ObjectKind(StrEnum):
    PROJECT = "project"
    REPOSITORY = "repository"
    PULL_REQUEST = "pull_request"
    USER = "user"


class BitbucketSelector(Selector):
    projects_filter: set[str] = Field(
        alias="projectsFilter",
        default_factory=set,
        description="List of project keys to filter. If empty, all projects will be synced",
    )
    pull_request_state: Literal["ALL", "OPEN", "MERGED", "DECLINED"] = Field(
        alias="pullRequestState",
        default="OPEN",
        description="State of pull requests to sync (ALL, OPEN, MERGED, DECLINED)",
    )


class BitbucketResourceConfig(ResourceConfig):
    selector: BitbucketSelector
    kind: Literal["project", "repository", "pull_request", "user"]


class BitbucketAppConfig(PortAppConfig):
    resources: list[BitbucketResourceConfig | ResourceConfig] = Field(
        default_factory=list,
    )


class BitbucketIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = BitbucketAppConfig
