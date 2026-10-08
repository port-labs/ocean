import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from port_ocean.context.resource import resource_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.exceptions.core import OceanAbortException

from plain.client import DEFAULT_API_URL
from plain.exceptions import PlainGraphQLError, PlainHTTPError

API_TOKEN = "plainApiKey_test"


def _config(api_url: str = DEFAULT_API_URL) -> dict[str, str]:
    return {"api_token": API_TOKEN, "api_url": api_url}


def _client(
    handler: Any,
    config: dict[str, str] | None = None,
) -> tuple[Any, httpx.AsyncClient]:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = config or _config()
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("plain.client.ocean", mock_ocean):
        from plain.client import PlainClient

        client = PlainClient(http_client=http_client)
    return client, http_client


@pytest.mark.asyncio
async def test_execute_returns_data_on_success() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["authorization"] = request.headers["authorization"]
        seen["retryable"] = request.extensions.get("retryable")
        return httpx.Response(
            200,
            json={"data": {"threads": {"totalCount": 1}}},
        )

    client, http_client = _client(handler)
    async with http_client:
        data = await client.execute(
            "query ListThreads($first: Int) { threads(first: $first) { totalCount } }",
            {"first": 1},
            operation_name="ListThreads",
        )

    assert data == {"threads": {"totalCount": 1}}
    assert seen["url"] == DEFAULT_API_URL
    assert seen["body"]["operationName"] == "ListThreads"
    assert seen["body"]["variables"] == {"first": 1}
    assert seen["authorization"] == f"Bearer {API_TOKEN}"
    assert seen["retryable"] is True


@pytest.mark.asyncio
async def test_execute_raises_on_graphql_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": None,
                "errors": [{"message": "Missing permission thread:read"}],
            },
        )

    client, http_client = _client(handler)
    async with http_client:
        with pytest.raises(PlainGraphQLError, match="Missing permission thread:read"):
            await client.execute("query { threads { id } }", {})


@pytest.mark.asyncio
async def test_execute_logs_missing_permission_and_fails_the_kind() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "errors": [
                    {
                        "message": 'Insufficient permissions, missing "timeline:read".',
                        "path": ["thread", "timelineEntries"],
                        "extensions": {"code": "FORBIDDEN"},
                    }
                ],
                "data": {"thread": None},
            },
        )

    client, http_client = _client(handler)
    config = ResourceConfig.parse_obj(
        {
            "kind": "thread-message",
            "selector": {"query": "true"},
            "port": {
                "entity": {
                    "mappings": {
                        "identifier": ".id",
                        "blueprint": '"plainThreadMessage"',
                    }
                }
            },
        }
    )
    async with http_client:
        with patch("plain.client.logger") as log:
            with pytest.raises(OceanAbortException, match="timeline:read"):
                async with resource_context(config):
                    await client.execute("query ThreadTimeline { thread { id } }", {})

    message = log.error.call_args.args[0]
    assert "thread-message" in message
    assert '"timeline:read"' in message
    log.exception.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 500])
async def test_execute_raises_on_http_errors(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"message": "Unauthorized"})

    client, http_client = _client(handler)
    async with http_client:
        with pytest.raises(PlainHTTPError, match=f"Plain API HTTP {status_code}"):
            await client.execute("query { threads { id } }", {})


@pytest.mark.asyncio
async def test_authorization_header_uses_token_from_config() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["authorization"]
        seen["user_agent"] = request.headers["user-agent"]
        return httpx.Response(200, json={"data": {"companies": {}}})

    client, http_client = _client(
        handler,
        {"api_token": "plainApiKey_from_config"},
    )
    async with http_client:
        await client.execute("query { companies { edges { node { id } } } }")

    assert seen["authorization"] == "Bearer plainApiKey_from_config"
    assert seen["user_agent"] == "port-ocean-plain"
