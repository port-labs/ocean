from typing import Literal

from pydantic import Field

from models import KomoObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration


class KomodorServiceResourceConfig(ResourceConfig):
    kind: Literal[KomoObjectKind.SERVICE] = Field(
        title="Komodor Service",
        description="Komodor service resource kind.",
    )


class KomodorHealthMonitoringResourceConfig(ResourceConfig):
    kind: Literal[KomoObjectKind.HEALTH_MONITOR] = Field(
        title="Komodor Health Monitoring",
        description="Komodor health monitoring resource kind.",
    )


class KomodorPortAppConfig(PortAppConfig):
    resources: list[
        KomodorServiceResourceConfig | KomodorHealthMonitoringResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]


class KomodorIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = KomodorPortAppConfig
