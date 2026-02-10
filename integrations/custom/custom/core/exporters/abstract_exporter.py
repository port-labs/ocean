from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

TClient = TypeVar("TClient")


class AbstractHttpExporter(Generic[TClient], ABC):
    """Abstract base class for custom integration resource exporters."""

    def __init__(self, client: TClient) -> None:
        self.client = client

    @abstractmethod
    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
