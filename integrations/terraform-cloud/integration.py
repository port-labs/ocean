from typing import Literal

from pydantic import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration

from utils import ObjectKind


class StateFileSelector(Selector):
    current_only: bool = Field(
        alias="currentOnly",
        default=True,
        title="Current Only",
        description="If true, fetch only the current state file per workspace. If false, fetch all historical state files.",
    )


class StateFileResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.STATE_FILE] = Field(
        title="Terraform State File",
        description="Terraform state file resource kind.",
    )
    selector: StateFileSelector = Field(
        title="Terraform State File Selector",
        description="Selector for the terraform state file resource.",
    )


class OrganizationResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.ORGANIZATION] = Field(
        title="Terraform Organization",
        description="Terraform organization resource kind.",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.PROJECT] = Field(
        title="Terraform Project",
        description="Terraform project resource kind.",
    )


class WorkspaceResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.WORKSPACE] = Field(
        title="Terraform Workspace",
        description="Terraform workspace resource kind.",
    )


class RunResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.RUN] = Field(
        title="Terraform Run",
        description="Terraform run resource kind.",
    )


class StateVersionResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.STATE_VERSION] = Field(
        title="Terraform State Version",
        description="Terraform state version resource kind.",
    )


class HealthAssessmentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.HEALTH_ASSESSMENT] = Field(
        title="Terraform Health Assessment",
        description="Terraform health assessment resource kind.",
    )


class TerraformCloudPortAppConfig(PortAppConfig):
    resources: list[
        StateFileResourceConfig
        | OrganizationResourceConfig
        | ProjectResourceConfig
        | WorkspaceResourceConfig
        | RunResourceConfig
        | StateVersionResourceConfig
        | HealthAssessmentResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class TerraformCloudIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = TerraformCloudPortAppConfig
