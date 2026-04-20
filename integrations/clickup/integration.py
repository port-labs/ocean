from typing import Literal, List
from pydantic import Field

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig

from clickup.helpers.utils import ObjectKind


class WorkspaceResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.WORKSPACE] = Field(
        description="ClickUp Workspace (Team in API v2)",
        title="Workspace",
    )


class SpaceResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.SPACE] = Field(
        description="ClickUp Space within a Workspace",
        title="Space",
    )


class FolderResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.FOLDER] = Field(
        description="ClickUp Folder within a Space",
        title="Folder",
    )


class ListResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.LIST] = Field(
        description="ClickUp List within a Folder or Space",
        title="List",
    )


class TaskResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.TASK] = Field(
        description="ClickUp Task within a List",
        title="Task",
    )


class ClickUpPortAppConfig(PortAppConfig):
    resources: List[
        WorkspaceResourceConfig
        | SpaceResourceConfig
        | FolderResourceConfig
        | ListResourceConfig
        | TaskResourceConfig
    ] = Field(
        description="ClickUp resources to sync",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]


class ClickUpIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ClickUpPortAppConfig
