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
            path="/analytics/ai-code/commits",
            params={"startDate": "1d", "endDate": "0d", "page": 1, "pageSize": 1},
        )

    assert response is success


@pytest.mark.asyncio
async def test_paginate_analytics_stops_when_total_exhausted(
    cursor_client: CursorClient,
) -> None:
    first_page = MagicMock(spec=httpx.Response)
    first_page.status_code = 200
    first_page.json.return_value = {
        "items": [{"commitHash": "a"}],
        "totalCount": 1,
        "page": 1,
        "pageSize": 100,
    }

    with patch.object(
        cursor_client,
        "_request_with_retry",
        new=AsyncMock(return_value=first_page),
    ):
        batches = [
            batch
            async for batch in cursor_client.get_ai_commit_metrics(
                {"startDate": "30d", "endDate": "0d", "page": 1, "pageSize": 100}
            )
        ]

    assert batches == [[{"commitHash": "a"}]]
