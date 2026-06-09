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
async def test_get_team_model_usage_yields_data(cursor_client: CursorClient) -> None:
    page = MagicMock(spec=httpx.Response)
    page.status_code = 200
    page.json.return_value = {
        "data": [
            {
                "date": "2026-05-10",
                "model_breakdown": {"default": {"messages": 5, "users": 2}},
            }
        ]
    }

    with patch.object(
        cursor_client,
        "_request_with_retry",
        new=AsyncMock(return_value=page),
    ):
        batches = [
            batch
            async for batch in cursor_client.get_team_model_usage(
                {"startDate": "30d", "endDate": "0d", "page": 1, "pageSize": 500}
            )
        ]

    assert batches == [
        [
            {
                "date": "2026-05-10",
                "model_breakdown": {"default": {"messages": 5, "users": 2}},
            }
        ]
    ]


@pytest.mark.asyncio
async def test_get_user_model_usage_flattens_and_paginates(
    cursor_client: CursorClient,
) -> None:
    first = MagicMock(spec=httpx.Response)
    first.status_code = 200
    first.json.return_value = {
        "data": {
            "a@port.io": [
                {"date": "2026-05-11", "model_breakdown": {"default": {"messages": 3}}}
            ],
            "b@port.io": [],
        },
        "pagination": {"page": 1, "totalPages": 2, "hasNextPage": True},
    }
    second = MagicMock(spec=httpx.Response)
    second.status_code = 200
    second.json.return_value = {
        "data": {
            "c@port.io": [
                {"date": "2026-05-12", "model_breakdown": {"default": {"messages": 9}}}
            ]
        },
        "pagination": {"page": 2, "totalPages": 2, "hasNextPage": False},
    }

    with patch.object(
        cursor_client,
        "_request_with_retry",
        new=AsyncMock(side_effect=[first, second]),
    ):
        batches = [
            batch
            async for batch in cursor_client.get_user_model_usage(
                {"startDate": "30d", "endDate": "0d", "page": 1, "pageSize": 50}
            )
        ]

    assert batches == [
        [
            {
                "userEmail": "a@port.io",
                "date": "2026-05-11",
                "model_breakdown": {"default": {"messages": 3}},
            }
        ],
        [
            {
                "userEmail": "c@port.io",
                "date": "2026-05-12",
                "model_breakdown": {"default": {"messages": 9}},
            }
        ],
    ]
