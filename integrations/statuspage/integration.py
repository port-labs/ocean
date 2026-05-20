from typing import Literal

from pydantic import Field

from kinds import ObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration


class StatuspagePageResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.PAGE] = Field(
        title="Statuspage Page",
        description="Statuspage page resource kind.",
    )


class ComponentGroupResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.COMPONENT_GROUPS] = Field(
        title="Statuspage Component Group",
        description="Statuspage component group resource kind.",
    )


class ComponentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.COMPONENT] = Field(
        title="Statuspage Component",
        description="Statuspage component resource kind.",
    )


class IncidentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.INCIDENT] = Field(
        title="Statuspage Incident",
        description="Statuspage incident resource kind.",
    )


class IncidentUpdateResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.INCIDENT_UPDATE] = Field(
        title="Statuspage Incident Update",
        description="Statuspage incident update resource kind.",
    )


class StatuspagePortAppConfig(PortAppConfig):
    resources: list[
        StatuspagePageResourceConfig
        | ComponentGroupResourceConfig
        | ComponentResourceConfig
        | IncidentResourceConfig
        | IncidentUpdateResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]


class StatuspageIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = StatuspagePortAppConfig
