import base64
from typing import Any

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from clients.cursor_client import CursorClient


@pytest.fixture
def cursor_client() -> CursorClient:
    return CursorClient(
        api_host="https://api.cursor.com",
        api_key="test-token",
        page_size=500,
        request_timeout_seconds=30,
    )


def _ok_response(payload: dict[str, Any]) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def test_client_uses_basic_authentication() -> None:
    client = CursorClient(api_host="https://api.cursor.com", api_key="secret")
    expected = base64.b64encode(b"secret:").decode()
    assert client._headers["Authorization"] == f"Basic {expected}"


def test_rate_limit_differs_per_api(cursor_client: CursorClient) -> None:
    admin = cursor_client._limiter_for("/teams/daily-usage-data")
    team = cursor_client._limiter_for("/analytics/team/models")
    by_user = cursor_client._limiter_for("/analytics/by-user/models")
    assert admin.max_rate == 20
    assert team.max_rate == 100
    assert by_user.max_rate == 50


@pytest.mark.asyncio
async def test_send_api_request_opts_into_transport_retry(
    cursor_client: CursorClient,
) -> None:
    mock_http_client = MagicMock()
    mock_http_client.request = AsyncMock(return_value=_ok_response({"data": [1, 2, 3]}))
    cursor_client._client = mock_http_client

    result = await cursor_client.send_api_request("POST", "/teams/daily-usage-data")

    assert result == {"data": [1, 2, 3]}
    # Retries (incl. 429/Retry-After) are delegated to the shared RetryTransport;
    # every request must opt in so POST endpoints are retried too.
    assert mock_http_client.request.call_args.kwargs["extensions"]["retryable"] is True


@pytest.mark.asyncio
async def test_send_api_request_raises_on_http_error(
    cursor_client: CursorClient,
) -> None:
    response = MagicMock(spec=httpx.Response)
    response.status_code = 500
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=MagicMock(), response=MagicMock()
    )
    mock_http_client = MagicMock()
    mock_http_client.request = AsyncMock(return_value=response)
    cursor_client._client = mock_http_client

    with pytest.raises(httpx.HTTPStatusError):
        await cursor_client.send_api_request("GET", "/analytics/team/models")


@pytest.mark.asyncio
async def test_send_paginated_request_walks_pages_with_total_pages(
    cursor_client: CursorClient,
) -> None:
    payloads = [
        {"data": {}, "pagination": {"totalPages": 2, "hasNextPage": True}},
        {"data": {}, "pagination": {"totalPages": 2, "hasNextPage": False}},
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
async def test_send_paginated_request_defaults_to_client_page_size(
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
            )
        ]

    body = mock_send.call_args_list[0].kwargs["json_body"]
    assert body["page"] == 1 and body["pageSize"] == 500
    assert mock_send.call_args_list[0].kwargs["params"] is None


@pytest.mark.asyncio
async def test_send_paginated_request_walks_pages_via_has_next_page(
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
            )
        ]

    assert pages == payloads


@pytest.mark.asyncio
async def test_send_paginated_request_propagates_exhausted_retry_error(
    cursor_client: CursorClient,
) -> None:
    # Once the shared RetryTransport has exhausted its attempts the error surfaces
    # here. The pages already yielded stay upserted and Ocean skips its delete
    # phase, so the tail is recovered on the next resync rather than being pruned.
    page1 = {"data": ["a"], "pagination": {"hasNextPage": True}}
    mock_send = AsyncMock(side_effect=[page1, httpx.ConnectError("down")])

    yielded = []
    with patch.object(cursor_client, "send_api_request", new=mock_send):
        with pytest.raises(httpx.ConnectError):
            async for page in cursor_client.send_paginated_request(
                "GET",
                "/analytics/by-user/models",
                params={"startDate": "30d", "endDate": "0d"},
            ):
                yielded.append(page)

    assert yielded == [page1]
