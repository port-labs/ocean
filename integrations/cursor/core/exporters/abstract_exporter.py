from abc import ABC, abstractmethod
from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.cursor_client import CursorClient


class AbstractCursorExporter(ABC):
    def __init__(self, client: CursorClient) -> None:
        self.client = client

    @abstractmethod
    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        pass
