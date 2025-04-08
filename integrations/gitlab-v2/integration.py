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

FILE_PROPERTY_PREFIX = "file://"
SEARCH_PROPERTY_PREFIX = "search://"
MAX_REQUESTS_PER_SECOND = 20


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
        default="",
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


class GitlabPortAppConfig(PortAppConfig):
    resources: list[
        GitLabFilesResourceConfig | ProjectResourceConfig | ResourceConfig
    ] = Field(default_factory=list)


class GitManipulationHandler(JQEntityProcessor):
    _rate_limiter = AsyncLimiter(MAX_REQUESTS_PER_SECOND, 1)

    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        async with self._rate_limiter:
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
