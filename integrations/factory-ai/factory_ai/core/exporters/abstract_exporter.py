from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from port_ocean.core.ocean_types import RAW_ITEM

from factory_ai.clients.factory_client import FactoryClient


class AbstractFactoryExporter[TListOptions, TGetOptions](ABC):
    """Abstract base class for Factory.ai resource exporters."""

    def __init__(self, client: FactoryClient) -> None:
        self.client = client

    @abstractmethod
    async def get_paginated_resources(
        self, options: TListOptions
    ) -> AsyncIterator[list[RAW_ITEM]]:
        if False:
            yield []
        raise NotImplementedError

    @abstractmethod
    async def get_resource(self, options: TGetOptions) -> RAW_ITEM | None:
        raise NotImplementedError
