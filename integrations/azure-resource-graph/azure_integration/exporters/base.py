from abc import ABC, abstractmethod
from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.clients.base import AbstractAzureClient


class BaseExporter(ABC):
    def __init__(
        self,
        client: AbstractAzureClient,
    ):
        self.client = client

    @abstractmethod
    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
