import pytest
from unittest.mock import AsyncMock, patch, MagicMock

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
            "azure_tenant_id" : "123"
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass

@pytest.mark.asyncio
async def test_get_all_subscriptions_success():
    client = AzureClient()
    mock_sub = SimpleNamespace(subscription_id="123")

    mock_subs_client = MagicMock()
    mock_subs_client.subscriptions.list = MagicMock(return_value=aiter([mock_sub]))
    client.subs_client = mock_subs_client

    subs = await client.get_all_subscriptions()
    assert len(subs) == 1
    assert subs[0].subscription_id == "123"


@pytest.mark.asyncio
async def test_get_all_subscriptions_not_initialized():
    client = AzureClient()
    client.subs_client = None

    with pytest.raises(ValueError, match="Azure client not initialized"):
        await client.get_all_subscriptions()


@pytest.mark.asyncio
async def test_run_query_single_page():
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
async def test_run_query_with_pagination():
    client = AzureClient()

    first_response = SimpleNamespace(data=[{"name": "page1"}], skip_token="token123")
    second_response = SimpleNamespace(data=[{"name": "page2"}], skip_token=None)

    mock_resource_client = MagicMock()
    mock_resource_client.resources = AsyncMock(side_effect=[first_response, second_response])
    client.resource_g_client = mock_resource_client

    results = []
    async for page in client.run_query("Test Query", ["sub1"]):
        results.extend(page)

    assert results == [{"name": "page1"}, {"name": "page2"}]
    assert mock_resource_client.resources.call_count == 2


@pytest.mark.asyncio
async def test_run_query_not_initialized():
    client = AzureClient()
    client.resource_g_client = None

    with pytest.raises(ValueError, match="Azure client not initialized"):
        async for _ in client.run_query("query", ["sub1"]):
            pass


@pytest.mark.asyncio
async def test_handle_rate_limit():
    await AzureClient._handle_rate_limit(False)
    await AzureClient._handle_rate_limit(True)  # Should return immediately


@pytest.mark.asyncio
@patch("clients.azure_client.ClientSecretCredential")
@patch("clients.azure_client.SubscriptionClient")
@patch("clients.azure_client.ResourceGraphClient")
async def test_context_manager(mock_resource_client, mock_subs_client, mock_creds):
    mock_subs_client.return_value.close = AsyncMock()
    mock_resource_client.return_value.close = AsyncMock()
    mock_creds.return_value.close = AsyncMock()

    client = AzureClient()
    async with client as ctx:
        assert ctx._credentials is not None
        assert ctx.subs_client is not None
        assert ctx.resource_g_client is not None

    ctx.subs_client.close.assert_awaited_once()
    ctx.resource_g_client.close.assert_awaited_once()
    ctx._credentials.close.assert_awaited_once()


# Utility for mocking async generators
def aiter(iterable):
    async def gen():
        for item in iterable:
            yield item
    return gen()
