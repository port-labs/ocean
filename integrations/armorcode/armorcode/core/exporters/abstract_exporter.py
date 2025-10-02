from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from armorcode.clients.http.armorcode_client import ArmorcodeClient


class AbstractArmorcodeExporter(ABC):
    """Abstract base class for ArmorCode exporters."""

    def __init__(self, client: ArmorcodeClient):
        self.client = client

    @abstractmethod
    async def get_paginated_resources(
        self, options: Optional[Dict[str, Any]] = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get paginated resources from the API."""

    @abstractmethod
    def get_resource_kind(self) -> str:
        """Get the resource kind this exporter handles."""
