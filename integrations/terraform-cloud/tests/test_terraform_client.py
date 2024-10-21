import asyncio
from typing import AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from client import TerraformClient, RATE_LIMIT_PER_SECOND
import time
import httpx


@pytest.fixture
def mock_http_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
async def terraform_client(
    mock_http_client: AsyncMock,
) -> AsyncGenerator[TerraformClient, None]:
    with patch("client.http_async_client", mock_http_client):
        client = TerraformClient("https://app.terraform.io", "test_token")
        client.rate_limit_lock = asyncio.Lock()
        # Manually set the headers to avoid the coroutine warning
        client.client.headers = httpx.Headers(client.base_headers)
        yield client


@pytest.mark.asyncio
async def test_wait_for_rate_limit(terraform_client: TerraformClient) -> None:
    current_time = time.time()
    with patch("time.time", side_effect=[current_time, current_time + 0.1]):
        with patch.object(asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
            # Simulate rate limit not reached
            terraform_client.request_times = [current_time - 0.1] * (
                RATE_LIMIT_PER_SECOND - 1
            )
            await terraform_client.wait_for_rate_limit()
            mock_sleep.assert_not_called()

            # Simulate rate limit reached
            terraform_client.request_times = [
                current_time - 0.1
            ] * RATE_LIMIT_PER_SECOND
            await terraform_client.wait_for_rate_limit()
            mock_sleep.assert_called_once()
            assert mock_sleep.call_args[0][0] > 0  # Ensure sleep time is positive

    # Test when wait time is not needed
    current_time = time.time()
    with patch("time.time", return_value=current_time):
        with patch.object(asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
            terraform_client.request_times = [
                current_time - 1.1
            ] * RATE_LIMIT_PER_SECOND
            await terraform_client.wait_for_rate_limit()
            mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_send_api_request(
    terraform_client: TerraformClient, mock_http_client: AsyncMock
) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": "test"}]}
    mock_response.headers = {
        "x-ratelimit-limit": "30",
        "x-ratelimit-remaining": "29",
        "x-ratelimit-reset": "1.0",
    }
    mock_http_client.request.return_value = mock_response

    result = await terraform_client.send_api_request("test_endpoint")

    expected_headers = {
        "Authorization": "Bearer test_token",
        "Content-Type": "application/vnd.api+json",
    }

    mock_http_client.request.assert_called_once_with(
        method="GET",
        url="https://app.terraform.io/api/v2/test_endpoint",
        params=None,
        json=None,
        headers=expected_headers,
    )

    assert result == {"data": [{"id": "test"}]}


@pytest.mark.asyncio
async def test_get_paginated_resources(terraform_client: TerraformClient) -> None:
    mock_responses = [
        {"data": [{"id": "1"}, {"id": "2"}], "links": {"next": "page2"}},
        {"data": [{"id": "3"}, {"id": "4"}], "links": {"next": None}},
    ]

    with patch.object(
        terraform_client, "send_api_request", side_effect=mock_responses
    ) as mock_send:
        results = []
        async for resources in terraform_client.get_paginated_resources(
            "test_endpoint"
        ):
            results.extend(resources)

        assert len(results) == 4
        assert [r["id"] for r in results] == ["1", "2", "3", "4"]
        assert mock_send.call_count == 2
