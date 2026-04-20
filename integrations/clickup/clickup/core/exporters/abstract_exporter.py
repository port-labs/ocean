from abc import ABC, abstractmethod
from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clickup.clients.http.clickup_client import ClickUpClient


class AbstractClickUpExporter[T: ClickUpClient](ABC):
    """Abstract base class for ClickUp exporters.

    Each exporter handles a specific resource kind and uses the client's
    generic HTTP methods to fetch data from the appropriate endpoints.
    """

    def __init__(self, client: T) -> None:
        self.client = client

    @abstractmethod
    def get_paginated_resources[
        AnyOptions: Any
    ](self, options: Optional[AnyOptions] = None) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Yield batches of resources from the API.

        Args:
            options: Optional configuration for the request

        Yields:
            Batches of raw resource dictionaries
        """
        ...

    @abstractmethod
    async def get_single_resource(self, resource_id: str) -> Optional[dict[str, Any]]:
        """Fetch a single resource by ID.

        Args:
            resource_id: The unique identifier of the resource

        Returns:
            The resource dictionary, or None if not found
        """
        ...
