from pydantic.fields import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration

class ServicenowSelector(Selector):
    path: str = Field(description="Servicenow Table API path to fetch data from")

class ServicenowResourceConfig(ResourceConfig):
    selector: ServicenowSelector


class ServicenowPortAppConfig(PortAppConfig):
    resources: list[ServicenowResourceConfig] = Field(default_factory=list)  # type: ignore


class ServicenowIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ServicenowPortAppConfig
