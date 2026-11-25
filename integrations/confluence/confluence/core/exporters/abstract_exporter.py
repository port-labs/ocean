from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Generic, TypeVar

from port_ocean.core.ocean_types import RAW_ITEM

TClient = TypeVar("TClient")


class AbstractConfluenceExporter(ABC, Generic[TClient]):
    """Fetches one Confluence resource kind through the generic HTTP client."""

    def __init__(self, client: TClient) -> None:
        self.client = client

    @abstractmethod
    async def get_paginated_resources(
        self, options: Any
    ) -> AsyncGenerator[list[RAW_ITEM], None]:
        """Yield batches of raw resources."""
        yield []

    @abstractmethod
    async def get_single_resource(self, resource_id: str) -> RAW_ITEM | None:
        """Fetch one resource by its Confluence id."""
