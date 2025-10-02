from typing import Literal, Optional

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration

from azure_integration.models import ResourceGroupTagFilters


class ResourceSelector(Selector):
    resource_types: Optional[list[str]] = None


class ResourceContainerSelector(Selector):
    tags: Optional[ResourceGroupTagFilters] = None


class AzureResourceConfig(ResourceConfig):
    selector: ResourceSelector
    kind: Literal["resource"]


class AzurePortAppConfig(PortAppConfig):
    resources: list[AzureResourceConfig | ResourceConfig]


class AzureIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AzurePortAppConfig
