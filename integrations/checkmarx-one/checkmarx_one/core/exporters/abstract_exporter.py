from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, Optional

from checkmarx_one.clients.base_client import CheckmarxOneClient as BaseCheckmarxClient


class AbstractCheckmarxExporter(ABC):
    """Abstract base class for Checkmarx One resource exporters."""

    def __init__(self, client: BaseCheckmarxClient) -> None:
        self.client = client

    @abstractmethod
    async def get_paginated_resources(
        self, options: Optional[Dict[str, Any]]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        pass

    @abstractmethod
    async def get_resource(self, options: Optional[Dict[str, Any]]) -> dict[str, Any]:
        pass
