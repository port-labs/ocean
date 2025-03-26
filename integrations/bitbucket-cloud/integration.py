from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

from typing import Literal
from pydantic import BaseModel, Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)


class RepositoryBranchMapping(BaseModel):
    name: str = Field(
        default="",
        alias="name",
        description="Specify the repository name",
    )
    branch: str = Field(
        default="default",
        alias="branch",
        description="Specify the branch to bring the folders from",
    )


class FolderPattern(BaseModel):
    path: str = Field(
        default="",
        alias="path",
        description="Specify the repositories and folders to include under this relative path",
    )
    repos: list[RepositoryBranchMapping] = Field(
        default_factory=list,
        alias="repos",
        description="Specify the repositories and branches to include under this relative path",
    )


class BitbucketFolderSelector(Selector):
    query: str = Field(default="", description="Query string to filter folders")
    folders: list[FolderPattern] = Field(
        default_factory=list,
        alias="folders",
        description="Specify the repositories, branches and folders to include under this relative path",
    )


class BitbucketFolderResourceConfig(ResourceConfig):
    kind: Literal["folder"]
    selector: BitbucketFolderSelector
    port: PortResourceConfig


class BitbucketFilePattern(BaseModel):
    path: str = Field(
        default="",
        alias="path",
        description="Specify the pattern or path to match files",
    )
    repos: list[str] = Field(
        default_factory=list,
        alias="repos",
        description="Specify the repositories to fetch files from",
    )
    skip_parsing: bool = Field(
        default=False,
        alias="skipParsing",
        description="Skip parsing the files and just return the raw file content",
    )
    depth: int = Field(
        default=20,
        alias="depth",
        description="Specify the depth of the files to fetch",
    )


class BitbucketFileSelector(Selector):
    files: BitbucketFilePattern


class BitbucketFileResourceConfig(ResourceConfig):
    kind: Literal["file"]
    selector: BitbucketFileSelector


class BitbucketAppConfig(PortAppConfig):
    resources: list[
        BitbucketFolderResourceConfig | BitbucketFileResourceConfig | ResourceConfig
    ] = Field(
        default_factory=list,
        alias="resources",
        description="Specify the resources to include in the sync",
    )


class BitbucketIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = BitbucketAppConfig
