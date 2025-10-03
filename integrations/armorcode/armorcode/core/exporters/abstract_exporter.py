from abc import ABC, abstractmethod
from typing import Any
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from armorcode.clients.http.armorcode_client import ArmorcodeClient


class AbstractArmorcodeExporter[T: ArmorcodeClient](ABC):
    """Abstract base class for ArmorCode exporters."""

    def __init__(self, client: T) -> None:
        self.client = client

    @abstractmethod
    def get_paginated_resources[
        AnyOptions: Any
    ](self, options: AnyOptions) -> ASYNC_GENERATOR_RESYNC_TYPE: ...

    @abstractmethod
    def get_resource_kind(self) -> str:
        """Get the resource kind this exporter handles."""
