from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from clients.claude_client import ClaudeClient, ClaudeDeployment


@pytest.fixture
def claude_client() -> ClaudeClient:
    client = ClaudeClient(
        api_host="https://api.anthropic.com",
        api_key="test-api-key",
        anthropic_version="2023-06-01",
        deployment=ClaudeDeployment.ENTERPRISE,
    )
    client._client = MagicMock()
    return client


# ---------------------------------------------------------------------------
# Deployment-aware headers
# ---------------------------------------------------------------------------


def test_enterprise_deployment_omits_anthropic_version() -> None:
    client = ClaudeClient(
        api_host="https://api.anthropic.com",
        api_key="test-api-key",
        anthropic_version="2023-06-01",
        deployment=ClaudeDeployment.ENTERPRISE,
    )
    assert "anthropic-version" not in client._headers


def test_platform_deployment_includes_anthropic_version() -> None:
    client = ClaudeClient(
        api_host="https://api.anthropic.com",
        api_key="test-api-key",
        anthropic_version="2023-06-01",
        deployment=ClaudeDeployment.PLATFORM,
    )
    assert client._headers["anthropic-version"] == "2023-06-01"


# ---------------------------------------------------------------------------
# _send_request
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# send_api_request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_api_request_returns_payload(claude_client: ClaudeClient) -> None:
    response = MagicMock()
    response.json.return_value = {"data": [{"id": "x"}]}

    with patch.object(
        claude_client, "_send_request", new=AsyncMock(return_value=response)
    ):
        payload = await claude_client.send_api_request("/v1/path", {"limit": 30})

    assert payload == {"data": [{"id": "x"}]}


# ---------------------------------------------------------------------------
# send_paginated_request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_paginate_follows_next_page_with_has_more(
    claude_client: ClaudeClient,
) -> None:
    send_mock = AsyncMock(
        side_effect=[
            {"data": [{"id": "record-1"}], "has_more": True, "next_page": "cursor-2"},
            {"data": [{"id": "record-2"}], "has_more": False, "next_page": None},
        ]
    )

    with patch.object(claude_client, "send_api_request", new=send_mock):
        results = [
            page
            async for page in claude_client.send_paginated_request(
                path="/v1/organizations/cost_report",
                params={"starting_at": "2026-01-01T00:00:00Z", "limit": 30},
            )
        ]

    assert results == [[{"id": "record-1"}], [{"id": "record-2"}]]
    assert send_mock.await_count == 2
    second_call = send_mock.await_args_list[1]
    assert second_call.kwargs["params"] == {
        "starting_at": "2026-01-01T00:00:00Z",
        "limit": 30,
        "page": "cursor-2",
    }


@pytest.mark.asyncio
async def test_paginate_follows_next_page_without_has_more(
    claude_client: ClaudeClient,
) -> None:
    """Users analytics endpoint only returns next_page (no has_more)."""
    send_mock = AsyncMock(
        side_effect=[
            {"data": [{"id": "u1"}], "next_page": "cursor-2"},
            {"data": [{"id": "u2"}], "next_page": None},
        ]
    )

    with patch.object(claude_client, "send_api_request", new=send_mock):
        results = [
            page
            async for page in claude_client.send_paginated_request(
                path="/v1/organizations/analytics/users",
                params={"date": "2026-03-05", "limit": 30},
            )
        ]

    assert results == [[{"id": "u1"}], [{"id": "u2"}]]
    assert send_mock.await_count == 2


@pytest.mark.asyncio
async def test_paginate_stops_when_payload_is_none(
    claude_client: ClaudeClient,
) -> None:
    with patch.object(
        claude_client, "send_api_request", new=AsyncMock(return_value=None)
    ):
        results = [
            page
            async for page in claude_client.send_paginated_request(
                path="/v1/path", params={}
            )
        ]

    assert results == []
