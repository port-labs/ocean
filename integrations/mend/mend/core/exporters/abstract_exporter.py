from abc import ABC, abstractmethod
from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from mend.clients.client import MendClient


class AbstractMendExporter(ABC):
    def __init__(self, client: MendClient) -> None:
        self.client = client

    @abstractmethod
    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        pass

    @abstractmethod
    async def get_resource(self, options: Any) -> RAW_ITEM:
        pass
