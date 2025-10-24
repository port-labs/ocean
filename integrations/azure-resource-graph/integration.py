from typing import Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field


class AzureAPIParams(Selector):
    api_version: str = Field(
        default="2024-04-01",
        description="The API version to use for the resource graph",
    )


class AzureResourceGraphSelector(AzureAPIParams):
    graph_query: str = Field(
        ...,
        alias="graphQuery",
        description="The Resource Graph query to use for the resource graph",
    )


class AzureResourceGraphConfig(ResourceConfig):
    selector: AzureResourceGraphSelector
    kind: Literal["resource", "resourceContainer"]


class AzurePortAppConfig(PortAppConfig):
    resources: list[AzureResourceGraphConfig | ResourceConfig] = Field(
        default_factory=list
    )


class AzureResourceGraphIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AzurePortAppConfig
