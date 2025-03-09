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
from bitbucket_integration.gitops.file_entity_handler import GitManipulationHandler


class FolderPattern(BaseModel):
    path: str = Field(
        default="",
        alias="path",
        description="Specify the repositories and folders to include under this relative path",
    )
    repos: list[str] = Field(
        default_factory=list,
        alias="repos",
        description="Specify the repositories to include under this relative path",
    )


class BitbucketFolderSelector(Selector):
    query: str = Field(default="", description="Query string to filter folders")
    folders: list[FolderPattern] = Field(
        default_factory=list,
        alias="folders",
        description="Specify the repositories and folders to include under this relative path",
    )


class BitbucketFolderResourceConfig(ResourceConfig):
    kind: Literal["folder"]
    selector: BitbucketFolderSelector
    port: PortResourceConfig


class BitbucketAppConfig(PortAppConfig):
    spec_path: str | list[str] = Field(alias="specPath", default="**/port.yaml")
    branch: str | None
    resources: list[BitbucketFolderResourceConfig | ResourceConfig] = Field(
        default_factory=list,
        alias="resources",
        description="Specify the resources to include in the sync",
    )


class BitbucketIntegration(BaseIntegration):
    EntityProcessorClass = GitManipulationHandler

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = BitbucketAppConfig
