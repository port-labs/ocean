from typing import Literal

from pydantic import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration

from kinds import ObjectKind


class AmplicationTemplateResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.TEMPLATE] = Field(
        title="Amplication Template",
        description="Amplication template resource kind.",
    )


class AmplicationResourceResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.RESOURCE] = Field(
        title="Amplication Resource",
        description="Amplication resource resource kind.",
    )


class AmplicationAlertResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.ALERT] = Field(
        title="Amplication Alert",
        description="Amplication alert resource kind.",
    )


class AmplicationPortAppConfig(PortAppConfig):
    resources: list[
        AmplicationTemplateResourceConfig
        | AmplicationResourceResourceConfig
        | AmplicationAlertResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]


class AmplicationIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AmplicationPortAppConfig
