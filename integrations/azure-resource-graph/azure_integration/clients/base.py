from __future__ import annotations

from abc import abstractmethod
from typing import Any, AsyncContextManager, AsyncGenerator, Protocol, Sequence


class ResponseObject(Protocol):
    data: Any


class AzureClient(AsyncContextManager["AzureClient"]):
    @abstractmethod
    async def make_request(
        self, query: str, subscriptions: Sequence[str], **kwargs: Any
    ) -> ResponseObject: ...

    @abstractmethod
    def make_paginated_request(
        self, query: str, subscriptions: Sequence[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]: ...
