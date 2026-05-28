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
    )
    client._client = MagicMock()
    return client


@pytest.mark.asyncio
async def test_send_request_success(claude_client: ClaudeClient) -> None:
    params = {"starting_at": "2026-01-01T00:00:00Z", "limit": 30}
    response = MagicMock()
    response.raise_for_status.return_value = None

    with patch.object(
        claude_client._client, "request", new=AsyncMock(return_value=response)
    ) as request_mock:
        result = await claude_client._send_request(
            "/v1/organizations/analytics/cost_report", params
        )

    assert result is response
    request_mock.assert_called_once_with(
        method="GET",
        url="https://api.anthropic.com/v1/organizations/analytics/cost_report",
        headers={
            "x-api-key": "test-api-key",
            "content-type": "application/json",
        },
        params=params,
    )


@pytest.mark.asyncio
async def test_send_request_returns_none_for_soft_fail_status(
    claude_client: ClaudeClient,
) -> None:
    request = httpx.Request(
        "GET", "https://api.anthropic.com/v1/organizations/analytics/users"
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
            "/v1/organizations/analytics/users",
            {},
            soft_fail_statuses={403},
        )

    assert result is None


@pytest.mark.asyncio
async def test_send_request_raises_retryable_status_without_manual_retry(
    claude_client: ClaudeClient,
) -> None:
    request = httpx.Request(
        "GET", "https://api.anthropic.com/v1/organizations/analytics/cost_report"
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
            await claude_client._send_request(
                "/v1/organizations/analytics/cost_report", {}
            )

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
                path="/v1/organizations/analytics/cost_report",
                params={"starting_at": "2026-01-01T00:00:00Z", "limit": 30},
            )
        ]

    assert results == [[{"id": "record-1"}], [{"id": "record-2"}]]
    assert send_request_mock.await_count == 2
    first_call = send_request_mock.await_args_list[0]
    second_call = send_request_mock.await_args_list[1]
    assert first_call.kwargs["params"] == {
        "starting_at": "2026-01-01T00:00:00Z",
        "limit": 30,
    }
    assert second_call.kwargs["params"] == {
        "starting_at": "2026-01-01T00:00:00Z",
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
async def test_get_usage_report_messages_uses_analytics_endpoint(
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
        "/v1/organizations/analytics/usage_report", {"limit": 30}
    )


@pytest.mark.asyncio
async def test_get_cost_report_uses_analytics_endpoint(
    claude_client: ClaudeClient,
) -> None:
    with patch.object(
        claude_client,
        "_paginate",
        return_value=_page_generator([{"id": "cost-1"}]),
    ) as paginate_mock:
        results = [page async for page in claude_client.get_cost_report({"limit": 30})]

    assert results == [[{"id": "cost-1"}]]
    paginate_mock.assert_called_once_with(
        "/v1/organizations/analytics/cost_report", {"limit": 30}
    )


@pytest.mark.asyncio
async def test_get_user_activity_soft_fails_on_403(
    claude_client: ClaudeClient,
) -> None:
    with patch.object(
        claude_client,
        "_paginate",
        return_value=_page_generator([{"id": "user-1"}]),
    ) as paginate_mock:
        results = [
            page async for page in claude_client.get_user_activity({"limit": 30})
        ]

    assert results == [[{"id": "user-1"}]]
    paginate_mock.assert_called_once_with(
        "/v1/organizations/analytics/users",
        {"limit": 30},
        soft_fail_statuses={403},
    )


@pytest.mark.asyncio
async def test_get_activity_summary_returns_list(
    claude_client: ClaudeClient,
) -> None:
    response = MagicMock()
    response.json.return_value = {"data": [{"dau": 10, "wau": 50}]}

    with patch.object(
        claude_client, "_send_request", new=AsyncMock(return_value=response)
    ):
        result = await claude_client.get_activity_summary(
            {"starting_date": "2026-01-01"}
        )

    assert result == [{"dau": 10, "wau": 50}]


@pytest.mark.asyncio
async def test_get_activity_summary_returns_empty_on_soft_fail(
    claude_client: ClaudeClient,
) -> None:
    with patch.object(
        claude_client, "_send_request", new=AsyncMock(return_value=None)
    ):
        result = await claude_client.get_activity_summary(
            {"starting_date": "2026-01-01"}
        )

    assert result == []


@pytest.mark.asyncio
async def test_get_user_usage_report_soft_fails_on_403(
    claude_client: ClaudeClient,
) -> None:
    with patch.object(
        claude_client,
        "_paginate",
        return_value=_page_generator([{"id": "uur-1"}]),
    ) as paginate_mock:
        results = [
            page async for page in claude_client.get_user_usage_report({"limit": 30})
        ]

    assert results == [[{"id": "uur-1"}]]
    paginate_mock.assert_called_once_with(
        "/v1/organizations/analytics/user_usage_report",
        {"limit": 30},
        soft_fail_statuses={403},
    )


@pytest.mark.asyncio
async def test_get_user_cost_report_soft_fails_on_403(
    claude_client: ClaudeClient,
) -> None:
    with patch.object(
        claude_client,
        "_paginate",
        return_value=_page_generator([{"id": "ucr-1"}]),
    ) as paginate_mock:
        results = [
            page async for page in claude_client.get_user_cost_report({"limit": 30})
        ]

    assert results == [[{"id": "ucr-1"}]]
    paginate_mock.assert_called_once_with(
        "/v1/organizations/analytics/user_cost_report",
        {"limit": 30},
        soft_fail_statuses={403},
    )
