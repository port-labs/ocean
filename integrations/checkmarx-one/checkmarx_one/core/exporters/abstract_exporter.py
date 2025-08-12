from abc import ABC, abstractmethod
from typing import Any

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE

from checkmarx_one.clients.client import CheckmarxOneClient


class AbstractCheckmarxExporter(ABC):
    """Abstract base class for Checkmarx One resource exporters."""

    def __init__(self, client: CheckmarxOneClient) -> None:
        self.client = client

    @abstractmethod
    async def get_paginated_resources(
        self, options: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        pass

    @abstractmethod
    async def get_resource(self, options: Any) -> RAW_ITEM:
        pass
