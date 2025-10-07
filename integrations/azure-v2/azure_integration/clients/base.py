from abc import abstractmethod
from typing import Any, AsyncContextManager, AsyncGenerator, Protocol, Sequence


class ResponseObject(Protocol):
    data: Any


class AzureClient(AsyncContextManager):
    @abstractmethod
    async def make_request(
        self, query: str, subscriptions: Sequence[str], **kwargs
    ) -> ResponseObject: ...

    @abstractmethod
    async def make_paginated_request(
        self, query: str, subscriptions: Sequence[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]: ...
