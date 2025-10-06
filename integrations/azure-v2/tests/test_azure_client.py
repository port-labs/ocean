from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.clients.client import AzureClient
from azure_integration.errors import AzureRequestThrottled, SubscriptionLimitReacheached
from tests.helpers import aiter


@pytest.mark.asyncio
async def test_get_all_subscriptions_success() -> None:
    client = AzureClient()
    mock_sub = SimpleNamespace(subscription_id="123")

    mock_subs_client = MagicMock()
    mock_subs_client.subscriptions.list = MagicMock(return_value=aiter([mock_sub]))
    client.subs_client = mock_subs_client

    subs = await client.get_all_subscriptions()
    assert len(subs) == 1
    assert subs[0].subscription_id == "123"


@pytest.mark.asyncio
async def test_get_all_subscriptions_not_initialized() -> None:
    client = AzureClient()
    client.subs_client = None

    with pytest.raises(ValueError, match="Azure client not initialized"):
        await client.get_all_subscriptions()


@pytest.mark.asyncio
async def test_run_query_single_page() -> None:
    client = AzureClient()
    mock_response = SimpleNamespace(data=[{"name": "resource1"}], skip_token=None)

    mock_resource_client = MagicMock()
    mock_resource_client.resources = AsyncMock(return_value=mock_response)
    client.resource_g_client = mock_resource_client

    results = []
    async for page in client.run_query("Test Query", ["sub1"]):
        results.extend(page)

    assert results == [{"name": "resource1"}]


@pytest.mark.asyncio
async def test_run_query_with_pagination() -> None:
    client = AzureClient()

    first_response = SimpleNamespace(data=[{"name": "page1"}], skip_token="token123")
    second_response = SimpleNamespace(data=[{"name": "page2"}], skip_token=None)

    mock_resource_client = MagicMock()
    mock_resource_client.resources = AsyncMock(
        side_effect=[first_response, second_response]
    )
    client.resource_g_client = mock_resource_client

    results = []
    async for page in client.run_query("Test Query", ["sub1"]):
        results.extend(page)

    assert results == [{"name": "page1"}, {"name": "page2"}]
    assert mock_resource_client.resources.call_count == 2


@pytest.mark.asyncio
async def test_run_query_not_initialized() -> None:
    client = AzureClient()
    client.resource_g_client = None

    with pytest.raises(ValueError, match="Azure client not initialized"):
        async for _ in client.run_query("query", ["sub1"]):
            pass


@pytest.mark.asyncio
async def test_handle_rate_limit() -> None:
    await AzureClient._handle_rate_limit(False)
    await AzureClient._handle_rate_limit(True)  # Should return immediately




async def test_run_query_throttling_handled() -> None:
    """Test that AzureRequestThrottled exception is handled and sleep is called."""
    client = AzureClient()
    client.resource_g_client = MagicMock()
    # Mock response with throttling headers
    mock_http_response = MagicMock()
    mock_http_response.headers = {
        "x-ms-user-quota-remaining": "0",
        "x-ms-user-quota-resets-after": "00:00:05",
        "x-ms-tenant-subscription-limit-hit": "false",
    }

    throttled_exception = AzureRequestThrottled(response=mock_http_response)

    # Mock the successful response after throttling
    mock_success_response = MagicMock()
    mock_success_response.data = [{"id": "resource-1"}]
    mock_success_response.skip_token = None

    client.resource_g_client.resources = AsyncMock(
        side_effect=[
            throttled_exception,
            mock_success_response,
        ]
    )

    query = "resources"
    subscriptions = ["sub-1"]

    with patch("azure_integration.errors.asyncio.sleep") as mock_sleep:
        results = []
        async for batch in client.run_query(query, subscriptions):
            results.extend(batch)

        mock_sleep.assert_called_once()
        sleep_duration_arg = mock_sleep.call_args[0][0]
        assert 6 <= sleep_duration_arg <= 10

        # Assert that the query eventually succeeded
        assert len(results) == 1
        assert results[0]["id"] == "resource-1"
        assert client.resource_g_client.resources.call_count == 2


@pytest.mark.asyncio
async def test_run_query_subscription_limit_reached() -> None:
    """Test that SubscriptionLimitReacheached is raised when the header is present."""
    # Mock response with subscription limit header
    client = AzureClient()
    client.resource_g_client = MagicMock()
    mock_http_response = MagicMock()
    mock_http_response.headers = {
        "x-ms-user-quota-remaining": "10",
        "x-ms-user-quota-resets-after": "00:01:00",
        "x-ms-tenant-subscription-limit-hit": "true",
    }

    throttled_exception = AzureRequestThrottled(response=mock_http_response)

    client.resource_g_client.resources.side_effect = [throttled_exception]

    query = "resources"
    subscriptions = ["sub-1"]

    with pytest.raises(SubscriptionLimitReacheached):
        async for _ in client.run_query(query, subscriptions):
            pass
