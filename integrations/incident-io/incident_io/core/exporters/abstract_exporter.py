from abc import ABC, abstractmethod
from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from incident_io.clients.client import IncidentIoClient


class AbstractIncidentIoExporter[T: IncidentIoClient](ABC):
    def __init__(self, client: T) -> None:
        self.client = client

    @abstractmethod
    def get_paginated_resources[
        Options: Any
    ](self, options: Options) -> ASYNC_GENERATOR_RESYNC_TYPE: ...

    @abstractmethod
    async def get_single_resource(
        self, resource_id: str, options: Any = None
    ) -> Optional[RAW_ITEM]: ...
