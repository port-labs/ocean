import base64

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from clients.cursor_client import CursorClient


@pytest.fixture
def cursor_client() -> CursorClient:
    return CursorClient(
        api_host="https://api.cursor.com",
        api_key="test-token",
        request_timeout_seconds=30,
        max_retries=2,
        backoff_seconds=0,
    )


def test_client_uses_basic_authentication() -> None:
    client = CursorClient(api_host="https://api.cursor.com", api_key="secret")
    expected = base64.b64encode(b"secret:").decode()
    assert client._headers["Authorization"] == f"Basic {expected}"


def test_invalid_api_host_is_rejected() -> None:
    with pytest.raises(ValueError):
        CursorClient(api_host="ftp://api.cursor.com", api_key="x")


def test_rate_limit_differs_per_api(cursor_client: CursorClient) -> None:
    admin = cursor_client._limiter_for("/teams/daily-usage-data")
    team = cursor_client._limiter_for("/analytics/team/models")
    by_user = cursor_client._limiter_for("/analytics/by-user/models")
    assert admin.max_rate == 20
    assert team.max_rate == 100
    assert by_user.max_rate == 50


@pytest.mark.asyncio
async def test_request_with_retry_retries_on_429(cursor_client: CursorClient) -> None:
    throttled = MagicMock(spec=httpx.Response)
    throttled.status_code = 429

    success = MagicMock(spec=httpx.Response)
    success.status_code = 200
    success.raise_for_status.return_value = None

    mock_http_client = MagicMock()
    mock_http_client.request = AsyncMock(side_effect=[throttled, success])
    cursor_client._client = mock_http_client
    with patch("clients.cursor_client.asyncio.sleep", new=AsyncMock()):
        response = await cursor_client._request_with_retry(
            method="GET",
            path="/analytics/team/models",
            params={"startDate": "1d", "endDate": "0d"},
        )

    assert response is success


@pytest.mark.asyncio
async def test_send_api_request_returns_parsed_json(
    cursor_client: CursorClient,
) -> None:
    response = MagicMock(spec=httpx.Response)
    response.json.return_value = {"data": [1, 2, 3]}

    with patch.object(
        cursor_client, "_request_with_retry", new=AsyncMock(return_value=response)
    ):
        result = await cursor_client.send_api_request("GET", "/analytics/team/models")

    assert result == {"data": [1, 2, 3]}


@pytest.mark.asyncio
async def test_send_paginated_request_walks_pages_and_injects_params(
    cursor_client: CursorClient,
) -> None:
    payloads = [
        {"data": {}, "pagination": {"hasNextPage": True}},
        {"data": {}, "pagination": {"hasNextPage": False}},
    ]
    mock_send = AsyncMock(side_effect=payloads)

    with patch.object(cursor_client, "send_api_request", new=mock_send):
        pages = [
            page
            async for page in cursor_client.send_paginated_request(
                "GET",
                "/analytics/by-user/models",
                params={"startDate": "30d", "endDate": "0d"},
                page_size=50,
            )
        ]

    assert pages == payloads
    first_params = mock_send.call_args_list[0].kwargs["params"]
    second_params = mock_send.call_args_list[1].kwargs["params"]
    assert first_params["page"] == 1 and first_params["pageSize"] == 50
    assert second_params["page"] == 2


@pytest.mark.asyncio
async def test_send_paginated_request_injects_page_into_body_for_post(
    cursor_client: CursorClient,
) -> None:
    mock_send = AsyncMock(
        return_value={"data": [], "pagination": {"hasNextPage": False}}
    )

    with patch.object(cursor_client, "send_api_request", new=mock_send):
        _ = [
            page
            async for page in cursor_client.send_paginated_request(
                "POST",
                "/teams/daily-usage-data",
                json_body={"startDate": 1, "endDate": 2},
                page_size=500,
            )
        ]

    body = mock_send.call_args_list[0].kwargs["json_body"]
    assert body["page"] == 1 and body["pageSize"] == 500
    assert mock_send.call_args_list[0].kwargs["params"] is None
