"""Abstract base class for Vercel resource exporters."""

from abc import ABC, abstractmethod
from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from vercel.clients.http.vercel_client import VercelClient


class AbstractVercelExporter(ABC):
    """Abstract base class for exporting Vercel resources."""

    def __init__(self, client: VercelClient) -> None:
        self.client = client

    @abstractmethod
    async def get_paginated_resources(
        self, options: Any = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get paginated resources from the Vercel API."""
        ...
