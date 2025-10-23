from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.clients.client import SDKClient
from azure_integration.errors import AzureRequestThrottled, SubscriptionLimitReacheached


@pytest.mark.asyncio
async def test_run_query_single_page() -> None:
    auth_cred = MagicMock()
    auth_cred.create_azure_credential.return_value.close = AsyncMock()
    client = SDKClient(auth_cred, MagicMock())
    mock_response = SimpleNamespace(data=[{"name": "resource1"}], skip_token=None)

    mock_resource_client = MagicMock()
    mock_resource_client.resources = AsyncMock(return_value=mock_response)
    mock_resource_client.close = AsyncMock()

    with patch(
        "azure_integration.clients.client.ResourceGraphClient",
        return_value=mock_resource_client,
    ):
        async with client:
            results = []
            async for page in client.make_paginated_request("Test Query", ["sub1"]):
                results.extend(page)

    assert results == [{"name": "resource1"}]


@pytest.mark.asyncio
async def test_run_query_with_pagination() -> None:
    auth_cred = MagicMock()
    auth_cred.create_azure_credential.return_value.close = AsyncMock()
    client = SDKClient(auth_cred, MagicMock())

    first_response = SimpleNamespace(data=[{"name": "page1"}], skip_token="token123")
    second_response = SimpleNamespace(data=[{"name": "page2"}], skip_token=None)

    mock_resource_client = MagicMock()
    mock_resource_client.resources = AsyncMock(
        side_effect=[first_response, second_response]
    )
    mock_resource_client.close = AsyncMock()

    with patch(
        "azure_integration.clients.client.ResourceGraphClient",
        return_value=mock_resource_client,
    ):
        async with client:
            results = []
            async for page in client.make_paginated_request("Test Query", ["sub1"]):
                results.extend(page)

    assert results == [{"name": "page1"}, {"name": "page2"}]
    assert mock_resource_client.resources.call_count == 2


@pytest.mark.asyncio
async def test_run_query_not_initialized() -> None:
    client = SDKClient(MagicMock(), MagicMock())
    client._resource_g_client = None

    with pytest.raises(
        ValueError,
        match="Azure Resource Graph Client not initialized, ensure SDKClient is run in a context manager",
    ):
        async for _ in client.make_paginated_request("query", ["sub1"]):
            pass


@pytest.mark.asyncio
async def test_handle_rate_limit() -> None:
    await SDKClient.handle_rate_limit(False)
    await SDKClient.handle_rate_limit(True)  # Should return immediately


@pytest.mark.asyncio
async def test_run_query_throttling_handled() -> None:
    """Test that AzureRequestThrottled exception is handled and sleep is called."""
    auth_cred = MagicMock()
    auth_cred.create_azure_credential.return_value.close = AsyncMock()
    client = SDKClient(auth_cred, MagicMock())
    mock_resource_client = MagicMock()
    mock_resource_client.close = AsyncMock()
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

    mock_resource_client.resources = AsyncMock(
        side_effect=[
            throttled_exception,
            mock_success_response,
        ]
    )

    query = "resources"
    subscriptions = ["sub-1"]

    with (
        patch(
            "azure_integration.clients.client.ResourceGraphClient",
            return_value=mock_resource_client,
        ),
        patch("azure_integration.errors.asyncio.sleep") as mock_sleep,
    ):
        async with client:
            results = []
            async for batch in client.make_paginated_request(query, subscriptions):
                results.extend(batch)

            mock_sleep.assert_called_once()
            sleep_duration_arg = mock_sleep.call_args[0][0]
            assert 6 <= sleep_duration_arg <= 10

            # Assert that the query eventually succeeded
            assert len(results) == 1
            assert results[0]["id"] == "resource-1"
            assert mock_resource_client.resources.call_count == 2


@pytest.mark.asyncio
async def test_run_query_subscription_limit_reached() -> None:
    """Test that SubscriptionLimitReacheached is raised when the header is present."""
    # Mock response with subscription limit header
    auth_cred = MagicMock()
    auth_cred.create_azure_credential.return_value.close = AsyncMock()
    client = SDKClient(auth_cred, MagicMock())
    mock_resource_client = MagicMock()
    mock_resource_client.close = AsyncMock()
    mock_http_response = MagicMock()
    mock_http_response.headers = {
        "x-ms-user-quota-remaining": "10",
        "x-ms-user-quota-resets-after": "00:01:00",
        "x-ms-tenant-subscription-limit-hit": "true",
    }

    throttled_exception = AzureRequestThrottled(response=mock_http_response)

    mock_resource_client.resources.side_effect = [throttled_exception]

    query = "resources"
    subscriptions = ["sub-1"]

    with (
        patch(
            "azure_integration.clients.client.ResourceGraphClient",
            return_value=mock_resource_client,
        ),
        pytest.raises(SubscriptionLimitReacheached),
    ):
        async with client:
            async for _ in client.make_paginated_request(query, subscriptions):
                pass
