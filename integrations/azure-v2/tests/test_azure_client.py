from typing import Any, AsyncGenerator, Iterable
import pytest
from unittest.mock import AsyncMock, MagicMock

from types import SimpleNamespace
from clients.azure_client import AzureClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "azure_client_id": "123",
            "azure_client_secret": "secret",
            "azure_tenant_id": "123",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


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


# Utility for mocking async generators
def aiter(iterable: Iterable[Any]) -> AsyncGenerator[Any, Any]:
    async def gen() -> AsyncGenerator[Any, Any]:
        for item in iterable:
            yield item

    return gen()
