from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE


class AbstractCheckmarxExporter(ABC):
    """Abstract base class for Checkmarx One resource exporters."""

    def __init__(self, client: Any) -> None:
        self.client = client

    @abstractmethod
    def get_paginated_resources(
        self, options: Optional[Mapping[str, Any]]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        pass

    @abstractmethod
    async def get_resource(self, options: Optional[Mapping[str, Any]]) -> RAW_ITEM:
        pass
