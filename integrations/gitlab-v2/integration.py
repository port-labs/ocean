from typing import Literal

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import BaseModel, Field

from processors.file_entity_processor import GitLabFileProcessor


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


class GitlabIntegration(BaseIntegration):
    EntityProcessorClass = GitLabFileProcessor

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitlabPortAppConfig
