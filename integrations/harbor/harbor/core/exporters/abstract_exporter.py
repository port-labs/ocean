from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from harbor.clients.http.harbor_client import HarborClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

T = TypeVar("T", bound=HarborClient)
AnyOption = TypeVar("AnyOption")


class AbstractHarborExporter(ABC, Generic[T]):
    def __init__(self, client: T) -> None:
        self.client = client

    @abstractmethod
    async def get_resource(self, options: Any) -> RAW_ITEM:
        pass

    @abstractmethod
    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        pass
