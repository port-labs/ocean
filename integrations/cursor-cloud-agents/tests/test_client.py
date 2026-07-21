from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from clients.cursor_agents_client import CursorAgentsClient
from clients.exceptions import CursorAgentsPaginationError


@pytest.fixture
def client() -> CursorAgentsClient:
    instance = CursorAgentsClient(
        api_host="https://api.cursor.com",
        api_key="test-api-key",
        console_host="https://cursor.com",
        page_size=2,
    )
    instance._client = AsyncMock()
    return instance


def test_basic_auth_header_is_base64_key_with_trailing_colon() -> None:
    instance = CursorAgentsClient(
        api_host="https://api.cursor.com",
        api_key="test-api-key",
        console_host="https://cursor.com",
    )
    assert instance._headers["Authorization"] == "Basic dGVzdC1hcGkta2V5Og=="


def test_console_host_strips_trailing_slash() -> None:
    instance = CursorAgentsClient(
        api_host="https://api.cursor.com",
        api_key="test-api-key",
        console_host="https://cursor.com/",
    )
    assert instance.get_console_host() == "https://cursor.com"


def test_page_size_property() -> None:
    instance = CursorAgentsClient(
        api_host="https://api.cursor.com",
        api_key="test-api-key",
        console_host="https://cursor.com",
        page_size=42,
    )
    assert instance.page_size == 42


@pytest.mark.asyncio
async def test_paginate_by_cursor_follows_next_cursor(
    client: CursorAgentsClient,
) -> None:
    responses = [
        {"items": [{"id": "a1"}, {"id": "a2"}], "nextCursor": "cursor_2"},
        {"items": [{"id": "a3"}]},
    ]
    client.send_api_request = AsyncMock(side_effect=responses)  # type: ignore[method-assign]

    batches = [
        batch async for batch in client.paginate_by_cursor("/v1/agents", "items")
    ]

    assert batches == [[{"id": "a1"}, {"id": "a2"}], [{"id": "a3"}]]
    assert client.send_api_request.await_count == 2
    second_call_params: dict[str, Any] = client.send_api_request.await_args_list[
        1
    ].kwargs["params"]
    assert second_call_params["cursor"] == "cursor_2"


@pytest.mark.asyncio
async def test_paginate_by_cursor_stops_and_raises_on_failure(
    client: CursorAgentsClient,
) -> None:
    client.send_api_request = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            {"items": [{"id": "a1"}], "nextCursor": "cursor_2"},
            httpx.HTTPStatusError(
                "boom", request=MagicMock(), response=MagicMock(status_code=500)
            ),
        ]
    )

    batches = []
    with pytest.raises(CursorAgentsPaginationError):
        async for batch in client.paginate_by_cursor("/v1/agents", "items"):
            batches.append(batch)

    assert batches == [[{"id": "a1"}]]


@pytest.mark.asyncio
async def test_send_api_request_returns_empty_dict_for_no_content(
    client: CursorAgentsClient,
) -> None:
    inner: Any = client._client
    response = httpx.Response(
        204, request=httpx.Request("GET", "https://api.cursor.com/v0/agents/a1")
    )
    inner.request = AsyncMock(return_value=response)

    result = await client.send_api_request("GET", "/v0/agents/a1")

    assert result == {}


@pytest.mark.asyncio
async def test_send_api_request_raises_logged_message_on_http_error(
    client: CursorAgentsClient,
) -> None:
    inner: Any = client._client
    request = httpx.Request("POST", "https://api.cursor.com/v1/agents")
    inner.request = AsyncMock(
        return_value=httpx.Response(
            400,
            text='{"error":{"code":"invalid_model","message":"bad variant"}}',
            request=request,
        )
    )

    with pytest.raises(httpx.HTTPStatusError, match="invalid_model.*bad variant"):
        await client.send_api_request("POST", "/v1/agents", json_body={"prompt": {}})
