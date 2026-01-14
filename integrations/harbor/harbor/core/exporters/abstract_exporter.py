"""Abstract exporter for Harbor resources."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, TypeVar

from harbor.clients.http.client import HarborClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


TClient = TypeVar("TClient", bound=HarborClient)


class AbstractHarborExporter(Generic[TClient], ABC):
    """Abstract base class for Harbor resource exporters."""

    def __init__(self, client: TClient) -> None:
        """Initialize the exporter with a Harbor client.

        Args:
            client: The Harbor client instance
        """
        self.client = client

    @staticmethod
    def _extract_items_from_response(response: Any) -> List[Dict[str, Any]]:
        """Extract items from Harbor API response.

        Harbor API returns lists directly for most endpoints, but may also
        return dicts with items/data/results keys.

        Args:
            response: The API response (list or dict)

        Returns:
            List of items extracted from the response
        """
        if isinstance(response, list):
            return response
        elif isinstance(response, dict):
            items = (
                response.get("items")
                or response.get("data")
                or response.get("results")
            )
            if isinstance(items, list):
                return items
            return []
        return []

    @abstractmethod
    async def get_resource(self, options: Any) -> RAW_ITEM:
        """Get a single resource.

        Args:
            options: Options for the request

        Returns:
            Resource data
        """
        ...

    @abstractmethod
    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get resources with pagination support.

        Args:
            options: Options for the request

        Yields:
            List of resources from each page
        """
        ...

