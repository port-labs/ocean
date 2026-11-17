from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from factory_ai.clients.factory_client import DEFAULT_FACTORY_API_HOST, FactoryClient


@pytest.fixture
def client() -> FactoryClient:
    instance = FactoryClient(
        api_host=DEFAULT_FACTORY_API_HOST,
        api_key="fk-test-key",
    )
    instance._client = AsyncMock()
    return instance


def test_bearer_auth_header() -> None:
    instance = FactoryClient(
        api_host=DEFAULT_FACTORY_API_HOST,
        api_key="fk-test-key",
    )
    assert instance._headers["Authorization"] == "Bearer fk-test-key"


def test_base_url_strips_trailing_slash() -> None:
    instance = FactoryClient(
        api_host="https://api.factory.ai/",
        api_key="fk-test-key",
    )
    assert instance.base_url == "https://api.factory.ai"


@pytest.mark.asyncio
async def test_send_api_request_success(client: FactoryClient) -> None:
    inner: Any = client._client
    request = httpx.Request("GET", "https://api.factory.ai/api/v0/sessions")
    inner.request = AsyncMock(
        return_value=httpx.Response(
            200, json={"sessions": [{"id": "s1"}]}, request=request
        )
    )

    result = await client.send_api_request("GET", "/api/v0/sessions")

    assert result == {"sessions": [{"id": "s1"}]}
    inner.request.assert_awaited_once()
    call_kwargs = inner.request.await_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer fk-test-key"
    assert call_kwargs["url"] == "https://api.factory.ai/api/v0/sessions"


@pytest.mark.asyncio
async def test_send_api_request_http_error_raises(client: FactoryClient) -> None:
    inner: Any = client._client
    request = httpx.Request("GET", "https://api.factory.ai/api/v0/sessions")
    inner.request = AsyncMock(
        return_value=httpx.Response(500, text="boom", request=request)
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.send_api_request("GET", "/api/v0/sessions")


@pytest.mark.asyncio
async def test_send_api_request_empty_body_returns_empty_dict(
    client: FactoryClient,
) -> None:
    inner: Any = client._client
    request = httpx.Request("DELETE", "https://api.factory.ai/api/v0/sessions/s1")
    inner.request = AsyncMock(
        return_value=httpx.Response(204, content=b"", request=request)
    )

    result = await client.send_api_request("DELETE", "/api/v0/sessions/s1")

    assert result == {}
