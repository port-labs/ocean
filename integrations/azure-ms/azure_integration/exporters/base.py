from abc import ABC, abstractmethod

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.clients.base import AzureClient
from azure_integration.helpers.subscription import SubscriptionManager


class BaseExporter(ABC):
    def __init__(
        self,
        client: AzureClient,
        resource_config: ResourceConfig,
        sub_manager: SubscriptionManager,
    ):
        self.client = client
        self.resource_config = resource_config
        self.sub_manager = sub_manager

    @abstractmethod
    async def export_single_resource(self) -> object: ...

    @abstractmethod
    def export_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
