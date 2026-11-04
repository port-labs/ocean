from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any


class BaseFoundryClient(ABC):
    PAGE_SIZE = 100

    @abstractmethod
    async def send_api_request(
        self,
        endpoint: str,
        *,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Send a request relative to a project endpoint base URL."""

    @abstractmethod
    async def send_paginated_request(
        self,
        project_endpoint: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield pages of dict items from a list-style Foundry API."""
