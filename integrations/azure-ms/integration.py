from typing import Literal, Optional

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from azure_integration.models import ResourceGroupTagFilters
from pydantic import Field


class TagSelector(Selector):
    tags: Optional[ResourceGroupTagFilters] = None


class ResourceSelector(TagSelector):
    resource_types: Optional[list[str]] = None


class ResourceContainerSelector(TagSelector):
    pass


class AzureResourceConfig(ResourceConfig):
    selector: ResourceSelector
    kind: Literal["resource"]


class AzureResourceContainerConfig(ResourceConfig):
    selector: ResourceContainerSelector
    kind: Literal["resourceContainer"]


class AzurePortAppConfig(PortAppConfig):
    resources: list[
        AzureResourceConfig | AzureResourceContainerConfig | ResourceConfig
    ] = Field(default_factory=list)


class AzureIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AzurePortAppConfig
