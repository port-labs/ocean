from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from port_ocean.core.ocean_types import RAW_ITEM

from client import CheckmarxClient


class AbstractCheckmarxExporter(ABC):
    """Abstract base class for Checkmarx One resource exporters."""

    def __init__(self, client: CheckmarxClient) -> None:
        self.client = client

    @abstractmethod
    async def get_resource[AnyOption: Any](self, options: AnyOption) -> RAW_ITEM:
        """Get a single resource by its identifier."""
        ...

    @abstractmethod
    def get_paginated_resources[
        AnyOption: Any
    ](self, options: AnyOption | None = None) -> AsyncIterator[list[dict[str, Any]]]:
        """Get paginated resources yielding batches."""
        ...
