from typing import Literal

from pydantic import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration

from utils import ObjectKind


class EnvironmentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.ENVIRONMENT] = Field(
        title="FireHydrant Environment",
        description="FireHydrant environment resource kind.",
    )


class ServiceResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.SERVICE] = Field(
        title="FireHydrant Service",
        description="FireHydrant service resource kind.",
    )


class IncidentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.INCIDENT] = Field(
        title="FireHydrant Incident",
        description="FireHydrant incident resource kind.",
    )


class RetrospectiveResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.RETROSPECTIVE] = Field(
        title="FireHydrant Retrospective",
        description="FireHydrant retrospective resource kind.",
    )


class FirehydrantPortAppConfig(PortAppConfig):
    resources: list[
        EnvironmentResourceConfig
        | ServiceResourceConfig
        | IncidentResourceConfig
        | RetrospectiveResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]


class FirehydrantIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = FirehydrantPortAppConfig
