from typing import Literal
from pydantic import BaseModel, Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

from github.helpers.utils import ObjectKind


class RepositoryBranchMapping(BaseModel):
    name: str = Field(
        default="",
        alias="name",
        description="Specify the repository name",
    )
    branch: str = Field(
        default="",
        alias="branch",
        description="Specify the branch to bring the folders from, repo's default branch will be used if none is passed",
    )


class FolderSelector(BaseModel):
    path: str = Field(default="*")
    repos: list[RepositoryBranchMapping]


class GithubFolderSelector(Selector):
    folders: list[FolderSelector]


class GithubFolderResourceConfig(ResourceConfig):
    selector: GithubFolderSelector
    kind: Literal[ObjectKind.FOLDER]


class GithubPortAppConfig(PortAppConfig):
    repository_type: str = Field(alias="repositoryType", default="all")
    resources: list[GithubFolderResourceConfig | ResourceConfig]


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
