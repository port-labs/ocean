from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient

TClient = TypeVar("TClient")


class AbstractFoundryExporter(ABC, Generic[TClient]):
    def __init__(self, client: TClient) -> None:
        self.client = client

    @abstractmethod
    async def get_paginated_resources(
        self, **options: object
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        pass
