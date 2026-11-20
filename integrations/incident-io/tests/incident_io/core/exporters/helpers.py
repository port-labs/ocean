from typing import Any, AsyncGenerator, AsyncIterator
from unittest.mock import AsyncMock, MagicMock


def mock_client(
    responses: dict[str, Any] | None = None,
    pages: list[list[dict[str, Any]]] | None = None,
) -> MagicMock:
    """Client double. `responses` maps an endpoint suffix to a JSON body.
    `pages` is what send_paginated_request yields."""

    async def send_api_request(endpoint: str, **kwargs: Any) -> Any:
        for suffix, body in (responses or {}).items():
            if endpoint.endswith(suffix):
                return body(kwargs) if callable(body) else body
        return {}

    async def send_paginated_request(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        client.paginated_calls.append((args, kwargs))
        for page in pages or []:
            yield page

    client = MagicMock()
    client.paginated_calls = []
    client.send_api_request = AsyncMock(side_effect=send_api_request)
    client.send_paginated_request = send_paginated_request
    return client


async def collect(gen: AsyncIterator[list[dict[Any, Any]]]) -> list[dict[Any, Any]]:
    return [item async for batch in gen for item in batch]
