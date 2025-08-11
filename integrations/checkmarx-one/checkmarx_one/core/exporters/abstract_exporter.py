from abc import ABC, abstractmethod
from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from checkmarx_one.clients.base_client import CheckmarxOneClient as BaseCheckmarxClient


class AbstractCheckmarxExporter(ABC):
    """Abstract base class for Checkmarx One resource exporters."""

    def __init__(self, client: BaseCheckmarxClient) -> None:
        self.client = client

    @abstractmethod
    async def get_paginated_resources[
        AnyOption: Any
    ](self, options: AnyOption) -> ASYNC_GENERATOR_RESYNC_TYPE:
        pass

    @abstractmethod
    async def get_resource[AnyOption: Any](self, options: AnyOption) -> RAW_ITEM:
        pass
