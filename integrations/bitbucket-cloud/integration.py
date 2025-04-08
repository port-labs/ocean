from port_ocean.core.handlers.entity_processor.jq_entity_processor import JQEntityProcessor
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from bitbucket_cloud.entity_processors.file_entity_processor import FileEntityProcessor
from typing import Any, Literal, Type
from pydantic import BaseModel, Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)


FILE_PROPERTY_PREFIX = "file://"

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
        description="Specify the path to match files from",
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
    filenames: list[str] = Field(
        default_factory=list,
        alias="filenames",
        description="Specify list of filenames to search and return",
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


class GitManipulationHandler(JQEntityProcessor):
    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = FileEntityProcessor
        else:
            entity_processor = JQEntityProcessor
        return await entity_processor(self.context)._search(data, pattern)


class BitbucketIntegration(BaseIntegration):
    EntityProcessorClass = GitManipulationHandler

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = BitbucketAppConfig
