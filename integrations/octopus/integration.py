from typing import ClassVar, Literal

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


class CustomResourceConfig(ResourceConfig):
    kind: str = Field(
        title="Custom Resource",
        description="Use this to map Octopus resources that have a list route in the <a target='_blank' href='https://samples.octopus.app/swaggerui/index.html'>Octopus API</a> in the form GET /{spaceId}/{resources} by setting the kind name to that resource name without the trailing s.\n\nExample: runbook for GET /{spaceId}/runbooks",
    )


class OctopusPortAppConfig(PortAppConfig):
    allow_custom_kinds: ClassVar[bool] = True
    resources: list[
        SpaceResourceConfig
        | ProjectResourceConfig
        | ReleaseResourceConfig
        | DeploymentResourceConfig
        | MachineResourceConfig
        | CustomResourceConfig
    ] = Field(
        title="Resources",
        description="The list of resource configurations for the integration.",
        default_factory=list,
    )  # type: ignore[assignment]


class OctopusIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = OctopusPortAppConfig
