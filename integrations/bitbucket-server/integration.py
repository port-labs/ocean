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
    PULL_REQUEST = "pull-request"
    USER = "user"


class BitbucketGenericSelector(Selector):
    projects: set[str] | None = Field(
        default=None,
        description="List of project keys to filter. If empty, all projects will be synced",
    )


class BitbucketPullRequestSelector(BitbucketGenericSelector):
    state: Literal["ALL", "OPEN", "MERGED", "DECLINED"] = Field(
        default="OPEN",
        description="State of pull requests to sync (ALL, OPEN, MERGED, DECLINED)",
    )


class BitbucketPullRequestResourceConfig(ResourceConfig):
    selector: BitbucketPullRequestSelector
    kind: Literal["pull-request"]


class BitbucketGenericResourceConfig(ResourceConfig):
    selector: BitbucketGenericSelector
    kind: Literal["project", "repository", "user"]


class BitbucketAppConfig(PortAppConfig):
    resources: list[
        BitbucketPullRequestResourceConfig
        | BitbucketGenericResourceConfig
        | ResourceConfig
    ] = Field(
        default_factory=list,
    )


class BitbucketIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = BitbucketAppConfig
