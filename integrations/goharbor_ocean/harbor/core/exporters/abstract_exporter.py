"""Abstract exporter for Harbor resources."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from harbor.clients.http.client import HarborClient

TClient = TypeVar("TClient", bound=HarborClient)


class AbstractHarborExporter(Generic[TClient], ABC):
    """Abstract base class for Harbor resource exporters."""

    def __init__(self, client: TClient) -> None:
        """Initialize the exporter with a Harbor client.

        Args:
            client: The Harbor client instance
        """
        self.client = client

    @abstractmethod
    async def get_resource(self, options: Any) -> RAW_ITEM:
        """Get a single resource."""

    @abstractmethod
    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get paginated resources."""
