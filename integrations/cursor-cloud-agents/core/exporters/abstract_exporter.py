from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from clients.cursor_agents_client import CursorAgentsClient


class AbstractCursorExporter(ABC):
    """Abstract base class for Cursor Cloud Agents resource exporters."""

    def __init__(self, client: CursorAgentsClient) -> None:
        self.client = client

    @abstractmethod
    async def get_paginated_resources(
        self, options: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        if False:
            yield []
        raise NotImplementedError

    async def get_resource(self, options: Any) -> dict[str, Any] | None:
        raise NotImplementedError
