from typing import Any, AsyncGenerator, Protocol, Sequence


class ResponseObject(Protocol):
    data: Any


class AzureClient(Protocol):
    async def make_request(
        self, query: str, subscriptions: Sequence[str], **kwargs
    ) -> ResponseObject: ...

    async def make_paginated_request(
        self, query: str, subscriptions: Sequence[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]: ...
