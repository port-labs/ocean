from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from factory_ai.clients.exceptions import FactoryAIError
from factory_ai.clients.factory_client import FactoryClient
from factory_ai.config import DEFAULT_FACTORY_API_HOST
from factory_ai.core.exporters.environment.models import (
    Environment,
    ListEnvironmentsResponse,
)


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


@pytest.mark.asyncio
async def test_get_parses_response_model(client: FactoryClient) -> None:
    inner: Any = client._client
    request = httpx.Request("GET", "https://api.factory.ai/api/v0/environments")
    payload = {
        "environments": [
            {
                "id": "env-1",
                "name": "Default",
                "repositories": [{"url": "https://github.com/acme/app", "script": ""}],
                "source": {
                    "id": "src-1",
                    "name": "Ubuntu",
                    "supportsRepositories": True,
                    "supportsSetupScripts": True,
                    "provider": {"id": "prov-1", "name": "Factory"},
                },
                "createdAt": 1_700_000_000_000,
                "updatedAt": 1_700_000_100_000,
            }
        ],
        "defaultEnvironmentId": "env-1",
    }
    inner.request = AsyncMock(
        return_value=httpx.Response(200, json=payload, request=request)
    )

    result = await client.get(
        "/api/v0/environments",
        ListEnvironmentsResponse,
        params={"serviceAccountId": "sa-1"},
    )

    assert isinstance(result, ListEnvironmentsResponse)
    assert result.default_environment_id == "env-1"
    assert result.environments[0].id == "env-1"
    assert result.environments[0].source.provider.name == "Factory"
    assert inner.request.await_args.kwargs["params"] == {"serviceAccountId": "sa-1"}


@pytest.mark.asyncio
async def test_get_invalid_payload_raises_factory_error(client: FactoryClient) -> None:
    inner: Any = client._client
    request = httpx.Request("GET", "https://api.factory.ai/api/v0/environments")
    inner.request = AsyncMock(
        return_value=httpx.Response(
            200, json={"environments": "not-a-list"}, request=request
        )
    )

    with pytest.raises(FactoryAIError, match="Invalid Factory response"):
        await client.get("/api/v0/environments", ListEnvironmentsResponse)


@pytest.mark.asyncio
async def test_get_or_none_returns_none_on_404(client: FactoryClient) -> None:
    inner: Any = client._client
    request = httpx.Request("GET", "https://api.factory.ai/api/v0/environments/missing")
    inner.request = AsyncMock(
        return_value=httpx.Response(404, text="not found", request=request)
    )

    result = await client.get_or_none("/api/v0/environments/missing", Environment)

    assert result is None


@pytest.mark.asyncio
async def test_get_or_none_still_raises_on_other_errors(client: FactoryClient) -> None:
    inner: Any = client._client
    request = httpx.Request("GET", "https://api.factory.ai/api/v0/environments/env-1")
    inner.request = AsyncMock(
        return_value=httpx.Response(500, text="boom", request=request)
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_or_none("/api/v0/environments/env-1", Environment)
