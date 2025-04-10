from typing import Literal, Any, Type

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import BaseModel, Field

from gitlab.entity_processors.file_entity_processor import FileEntityProcessor
from gitlab.entity_processors.search_entity_processor import SearchEntityProcessor
from port_ocean.core.handlers import JQEntityProcessor
from aiolimiter import AsyncLimiter
import asyncio

FILE_PROPERTY_PREFIX = "file://"
SEARCH_PROPERTY_PREFIX = "search://"
MAX_REQUESTS_PER_TIME_WINDOW = 10
_rate_limiter = AsyncLimiter(MAX_REQUESTS_PER_TIME_WINDOW, 0.25)
_semaphore = asyncio.Semaphore(5)


class ProjectSelector(Selector):
    include_languages: bool = Field(
        alias="includeLanguages",
        default=False,
        description="Whether to include the languages of the project, defaults to false",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal["project"]
    selector: ProjectSelector


class FilesSelector(BaseModel):
    path: str = Field(
        alias="path",
        description="Specify the path to match files from",
    )
    repos: list[str] = Field(
        description="A list of repositories to search files in", default_factory=list
    )
    skip_parsing: bool = Field(
        default=False,
        alias="skipParsing",
        description="Skip parsing the files and just return the raw file content",
    )


class GitLabFilesSelector(Selector):
    files: FilesSelector


class GitLabFilesResourceConfig(ResourceConfig):
    selector: GitLabFilesSelector
    kind: Literal["file"]


class RepositoryBranchMapping(BaseModel):
    name: str = Field(
        default="",
        alias="name",
        description="Specify the repository name",
    )
    branch: str = Field(
        default="main",
        alias="branch",
        description="Specify the branch to bring the folders from",
    )


class FolderPattern(BaseModel):
    path: str = Field(
        alias="path",
        description="Specify the repositories and folders to include under this relative path",
    )
    repos: list[RepositoryBranchMapping] = Field(
        default_factory=list,
        alias="repos",
        description="Specify the repositories and branches to include under this relative path",
    )


class GitlabFolderSelector(Selector):
    folders: list[FolderPattern] = Field(
        default_factory=list,
        alias="folders",
        description="Specify the repositories, branches and folders to include under this relative path",
    )


class GitLabFoldersResourceConfig(ResourceConfig):
    selector: GitlabFolderSelector
    kind: Literal["folder"]


class GitlabPortAppConfig(PortAppConfig):
    resources: list[
        GitLabFoldersResourceConfig
        | GitLabFilesResourceConfig
        | ProjectResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)


class GitManipulationHandler(JQEntityProcessor):
    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]

        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = FileEntityProcessor
        elif pattern.startswith(SEARCH_PROPERTY_PREFIX):
            entity_processor = SearchEntityProcessor
        else:
            entity_processor = JQEntityProcessor

        return await entity_processor(self.context)._search(data, pattern)


class GitlabIntegration(BaseIntegration):
    EntityProcessorClass = GitManipulationHandler

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitlabPortAppConfig
