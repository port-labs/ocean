from typing import Literal

from pydantic import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration

from utils import ObjectKind


class SpaceResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.SPACE] = Field(
        title="Octopus Space",
        description="Octopus Deploy space resource kind.",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.PROJECT] = Field(
        title="Octopus Project",
        description="Octopus Deploy project resource kind.",
    )


class ReleaseResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.RELEASE] = Field(
        title="Octopus Release",
        description="Octopus Deploy release resource kind.",
    )


class DeploymentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.DEPLOYMENT] = Field(
        title="Octopus Deployment",
        description="Octopus Deploy deployment resource kind.",
    )


class MachineResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.MACHINE] = Field(
        title="Octopus Machine",
        description="Octopus Deploy machine resource kind.",
    )


class OctopusPortAppConfig(PortAppConfig):
    resources: list[
        SpaceResourceConfig
        | ProjectResourceConfig
        | ReleaseResourceConfig
        | DeploymentResourceConfig
        | MachineResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]


class OctopusIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = OctopusPortAppConfig
