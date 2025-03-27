from typing import Literal

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import BaseModel, Field

from gitops.file_entity_processor import GitLabFileProcessor


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
    path: str = Field(description="The path to get the files from")
    repos: list[str] = Field(
        description="A list of repositories to search files in", default_factory=list
    )


class GitLabFilesSelector(Selector):
    files: FilesSelector


class GitLabFilesResourceConfig(ResourceConfig):
    selector: GitLabFilesSelector
    kind: Literal["file"]


class FoldersSelector(BaseModel):
    path: str
    repos: list[str] = Field(default_factory=list)
    branch: str | None = None


class GitlabFolderSelector(Selector):
    folders: list[FoldersSelector] = Field(default_factory=list)


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


class GitlabIntegration(BaseIntegration):
    EntityProcessorClass = GitLabFileProcessor

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitlabPortAppConfig
