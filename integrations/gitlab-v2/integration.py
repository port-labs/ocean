from typing import Literal
from gitops.file_entity_processor import GitLabFileProcessor
from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field, BaseModel


class ProjectSelector(Selector):
    include_labels: bool = Field(
        alias="includeLabels",
        default=False,
        description="Whether to include the labels of the project, defaults to false",
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


class GitlabPortAppConfig(PortAppConfig):
    resources: list[
        GitLabFilesResourceConfig | ProjectResourceConfig | ResourceConfig
    ] = Field(default_factory=list)


class GitlabIntegration(BaseIntegration):
    EntityProcessorClass = GitLabFileProcessor

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitlabPortAppConfig
