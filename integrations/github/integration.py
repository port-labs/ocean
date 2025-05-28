from pydantic import BaseModel, Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

from github.helpers.utils import ObjectKind


class FolderSelector(BaseModel):
    path: str = Field(default="*")
    repos: list[str]


class GithubFolderSelector(Selector):
    folders: list[FolderSelector]


class GithubFolderResourceConfig(ResourceConfig):
    selector: GithubFolderSelector
    kind: ObjectKind.FOLDER


class GithubPortAppConfig(PortAppConfig):
    repository_type: str = Field(alias="repositoryType", default="all")
    resources: list[ResourceConfig | GithubFolderResourceConfig]


class GithubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
