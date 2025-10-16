from abc import ABC, abstractmethod
from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.clients.base import AzureClient
from azure_integration.helpers.subscription import SubscriptionManager


class BaseExporter(ABC):
    def __init__(
        self,
        client: AzureClient,
        sub_manager: SubscriptionManager,
    ):
        self.client = client
        self.sub_manager = sub_manager

    @abstractmethod
    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
