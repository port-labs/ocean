from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from clients.claude_client import ClaudeClient


def _page_generator(
    *pages: list[dict[str, object]]
) -> AsyncGenerator[list[dict[str, object]], None]:
    async def _generator() -> AsyncGenerator[list[dict[str, object]], None]:
        for page in pages:
            yield page

    return _generator()


@pytest.fixture
def claude_client() -> ClaudeClient:
    client = ClaudeClient(
        api_host="https://api.anthropic.com",
        api_key="test-api-key",
        anthropic_version="2023-06-01",
    )
    client._client = MagicMock()
    return client


@pytest.mark.asyncio
async def test_send_request_success(claude_client: ClaudeClient) -> None:
    params = {"starting_at": "2025-01-01T00:00:00Z", "limit": 30}
    response = MagicMock()
    response.raise_for_status.return_value = None

    with patch.object(
        claude_client._client, "request", new=AsyncMock(return_value=response)
    ) as request_mock:
        result = await claude_client._send_request(
            "/v1/organizations/cost_report", params
        )

    assert result is response
    request_mock.assert_called_once_with(
        method="GET",
        url="https://api.anthropic.com/v1/organizations/cost_report",
        headers={
            "x-api-key": "test-api-key",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        params=params,
    )


@pytest.mark.asyncio
async def test_send_request_returns_none_for_404(claude_client: ClaudeClient) -> None:
    request = httpx.Request(
        "GET", "https://api.anthropic.com/v1/organizations/cost_report"
    )
    response = httpx.Response(status_code=404, request=request)
    request_mock = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Not found",
            request=request,
            response=response,
        )
    )

    with patch.object(claude_client._client, "request", new=request_mock):
        result = await claude_client._send_request("/v1/organizations/cost_report", {})

    assert result is None


@pytest.mark.asyncio
async def test_send_request_returns_none_for_soft_fail_status(
    claude_client: ClaudeClient,
) -> None:
    request = httpx.Request(
        "GET", "https://api.anthropic.com/v1/organizations/usage_report/claude_code"
    )
    response = httpx.Response(status_code=403, request=request)
    request_mock = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Forbidden",
            request=request,
            response=response,
        )
    )

    with patch.object(claude_client._client, "request", new=request_mock):
        result = await claude_client._send_request(
            "/v1/organizations/usage_report/claude_code",
            {},
            soft_fail_statuses={403},
        )

    assert result is None


@pytest.mark.asyncio
async def test_send_request_raises_retryable_status_without_manual_retry(
    claude_client: ClaudeClient,
) -> None:
    request = httpx.Request(
        "GET", "https://api.anthropic.com/v1/organizations/cost_report"
    )
    response = httpx.Response(status_code=429, request=request)
    request_mock = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Too many requests",
            request=request,
            response=response,
        )
    )

    with patch.object(claude_client._client, "request", new=request_mock):
        with pytest.raises(httpx.HTTPStatusError):
            await claude_client._send_request("/v1/organizations/cost_report", {})

    request_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_paginate_follows_next_page_cursor(claude_client: ClaudeClient) -> None:
    first_response = MagicMock()
    first_response.json.return_value = {
        "data": [{"id": "record-1"}],
        "has_more": True,
        "next_page": "cursor-2",
    }
    second_response = MagicMock()
    second_response.json.return_value = {
        "data": [{"id": "record-2"}],
        "has_more": False,
    }

    send_request_mock = AsyncMock(side_effect=[first_response, second_response])

    with patch.object(claude_client, "_send_request", new=send_request_mock):
        results = [
            page
            async for page in claude_client._paginate(
                path="/v1/organizations/cost_report",
                params={"starting_at": "2025-01-01T00:00:00Z", "limit": 30},
            )
        ]

    assert results == [[{"id": "record-1"}], [{"id": "record-2"}]]
    assert send_request_mock.await_count == 2
    first_call = send_request_mock.await_args_list[0]
    second_call = send_request_mock.await_args_list[1]
    assert first_call.kwargs["params"] == {
        "starting_at": "2025-01-01T00:00:00Z",
        "limit": 30,
    }
    assert second_call.kwargs["params"] == {
        "starting_at": "2025-01-01T00:00:00Z",
        "limit": 30,
        "page": "cursor-2",
    }


@pytest.mark.asyncio
async def test_paginate_stops_on_unexpected_payload_shape(
    claude_client: ClaudeClient,
) -> None:
    response = MagicMock()
    response.json.return_value = [{"id": "unexpected-list"}]

    with patch.object(
        claude_client, "_send_request", new=AsyncMock(return_value=response)
    ):
        results = [
            page async for page in claude_client._paginate(path="/v1/path", params={})
        ]

    assert results == []


@pytest.mark.asyncio
async def test_get_usage_report_messages_uses_messages_endpoint(
    claude_client: ClaudeClient,
) -> None:
    with patch.object(
        claude_client,
        "_paginate",
        return_value=_page_generator([{"id": "usage-1"}]),
    ) as paginate_mock:
        results = [
            page
            async for page in claude_client.get_usage_report_messages({"limit": 30})
        ]

    assert results == [[{"id": "usage-1"}]]
    paginate_mock.assert_called_once_with(
        "/v1/organizations/usage_report/messages", {"limit": 30}
    )


@pytest.mark.asyncio
async def test_get_cost_report_uses_cost_endpoint(claude_client: ClaudeClient) -> None:
    with patch.object(
        claude_client,
        "_paginate",
        return_value=_page_generator([{"id": "cost-1"}]),
    ) as paginate_mock:
        results = [page async for page in claude_client.get_cost_report({"limit": 30})]

    assert results == [[{"id": "cost-1"}]]
    paginate_mock.assert_called_once_with(
        "/v1/organizations/cost_report", {"limit": 30}
    )


@pytest.mark.asyncio
async def test_get_claude_code_report_soft_fails_on_403(
    claude_client: ClaudeClient,
) -> None:
    with patch.object(
        claude_client,
        "_paginate",
        return_value=_page_generator([{"id": "code-1"}]),
    ) as paginate_mock:
        results = [
            page async for page in claude_client.get_claude_code_report({"limit": 30})
        ]

    assert results == [[{"id": "code-1"}]]
    paginate_mock.assert_called_once_with(
        "/v1/organizations/usage_report/claude_code",
        {"limit": 30},
        soft_fail_statuses={403},
    )
