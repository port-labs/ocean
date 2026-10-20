from abc import ABC, abstractmethod
from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from clients.devin_client import DevinClient


class AbstractDevinExporter(ABC):
    """Abstract base class for Devin resource exporters."""

    def __init__(self, client: DevinClient) -> None:
        self.client = client

    @abstractmethod
    def get_paginated_resources(self, **options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        pass

    @abstractmethod
    async def get_resource(self, resource_id: str) -> RAW_ITEM:
        pass
