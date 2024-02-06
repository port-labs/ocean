from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.fields import Field


class DynatraceEntitySelector(Selector):
    entity_types: list[str] = Field(
        default=["APPLICATION", "SERVICE"],
        description="List of entity types to be fetched",
        alias="entityTypes",
    )


class DynatraceResourceConfig(ResourceConfig):
    selector: DynatraceEntitySelector


class DynatracePortAppConfig(PortAppConfig):
    resources: list[DynatraceResourceConfig] = Field(default_factory=list)  # type: ignore


class DynatraceIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DynatracePortAppConfig
