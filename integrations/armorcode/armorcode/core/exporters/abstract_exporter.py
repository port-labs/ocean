from abc import ABC, abstractmethod
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from ...clients.http.armorcode_client import ArmorcodeClient


class AbstractArmorcodeExporter(ABC):
    """Abstract base class for ArmorCode exporters."""

    def __init__(self, client: ArmorcodeClient):
        self.client = client

    @abstractmethod
    async def get_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get paginated resources from the API."""

    @abstractmethod
    def get_resource_kind(self) -> str:
        """Get the resource kind this exporter handles."""
