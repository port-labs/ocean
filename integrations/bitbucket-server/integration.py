from enum import StrEnum
from typing import Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field


class ObjectKind(StrEnum):
    PROJECT = "project"
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    USER = "user"


class BitbucketGenericSelector(Selector):
    projects: set[str] | None = Field(
        default=None,
        title="Projects",
        description="List of project keys to filter. If empty, all projects will be synced",
    )
    projectFilterRegex: str | None = Field(
        default=None,
        alias="projectFilterRegex",
        title="Project Filter Regex",
        description="Optional regex pattern to filter project keys (e.g., '^PROJ-.*' to include only projects starting with 'PROJ-', or '.*-PROD$' to include only projects ending with '-PROD')",
    )


class BitbucketPullRequestSelector(BitbucketGenericSelector):
    state: Literal["ALL", "OPEN", "MERGED", "DECLINED"] = Field(
        default="OPEN",
        title="State",
        description="State of pull requests to sync (ALL, OPEN, MERGED, DECLINED)",
    )


class BitbucketProjectResourceConfig(ResourceConfig):
    selector: BitbucketGenericSelector = Field(
        title="Project Selector",
        description="Selector for the Bitbucket project resource.",
    )
    kind: Literal["project"] = Field(
        title="Bitbucket Project",
        description="Bitbucket project resource kind.",
    )


class BitbucketRepositoryResourceConfig(ResourceConfig):
    selector: BitbucketGenericSelector = Field(
        title="Repository Selector",
        description="Selector for the Bitbucket repository resource.",
    )
    kind: Literal["repository"] = Field(
        title="Bitbucket Repository",
        description="Bitbucket repository resource kind.",
    )


class BitbucketUserResourceConfig(ResourceConfig):
    selector: BitbucketGenericSelector = Field(
        title="User Selector",
        description="Selector for the Bitbucket user resource.",
    )
    kind: Literal["user"] = Field(
        title="Bitbucket User",
        description="Bitbucket user resource kind.",
    )


class BitbucketPullRequestResourceConfig(ResourceConfig):
    selector: BitbucketPullRequestSelector = Field(
        title="Pull Request Selector",
        description="Selector for the Bitbucket pull request resource.",
    )
    kind: Literal["pull-request"] = Field(
        title="Bitbucket Pull Request",
        description="Bitbucket pull request resource kind.",
    )


class BitbucketAppConfig(PortAppConfig):
    resources: list[
        BitbucketProjectResourceConfig
        | BitbucketRepositoryResourceConfig
        | BitbucketUserResourceConfig
        | BitbucketPullRequestResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class BitbucketIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = BitbucketAppConfig
