from enum import StrEnum
from typing import Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import BaseModel, Field


class ObjectKind(StrEnum):
    PROJECT = "project"
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    USER = "user"
    FOLDER = "folder"
    FILE = "file"


class BitbucketServerFilePattern(BaseModel):
    path: str = Field(
        default="",
        description="Specify the path to match files from",
    )
    repos: list[str] = Field(
        default_factory=list,
        description="Specify the repositories to fetch files from",
    )
    project_key: str = Field(
        default="",
        description="Project key containing the repositories",
    )
    skip_parsing: bool = Field(
        default=False,
        description="Skip parsing the files and just return the raw file content",
    )
    filenames: list[str] = Field(
        default_factory=list,
        description="Specify list of filenames to search and return",
    )

class BitbucketServerFileSelector(Selector):
    files: BitbucketServerFilePattern

class BitbucketServerFileResourceConfig(ResourceConfig):
    kind: Literal["file"]
    selector: BitbucketServerFileSelector

class BitbucketServerFolderPattern(BaseModel):
    path: str = Field(
        default="",
        description="Specify the path to match folders from",
    )
    repos: list[str] = Field(
        default_factory=list,
        description="Specify the repositories to include",
    )
    project_key: str = Field(
        default="",
        description="Project key containing the repositories",
    )

class BitbucketServerFolderSelector(Selector):
    folders: list[BitbucketServerFolderPattern] = Field(
        default_factory=list,
        description="Folder patterns to match",
    )

class BitbucketServerFolderResourceConfig(ResourceConfig):
    kind: Literal["folder"]
    selector: BitbucketServerFolderSelector

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
        | BitbucketServerFolderResourceConfig
        | BitbucketServerFileResourceConfig
        | ResourceConfig
    ] = Field(
        default_factory=list,
    )


class BitbucketIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = BitbucketAppConfig