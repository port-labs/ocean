from unittest.mock import AsyncMock, PropertyMock, MagicMock

import pytest

from azure_integration.clients.base import AzureRequest
from azure_integration.clients.rest.resource_management_client import (
    AzureResourceManagerClient,
)
from tests.conftest import _DummyCredential, _NoOpRateLimiter


@pytest.mark.asyncio
async def test_make_paginated_request_with_nextlink(
    dummy_credential: _DummyCredential,
    noop_rate_limiter: _NoOpRateLimiter,
    mock_httpx_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = "https://management.azure.com"
    endpoint = "subscriptions"
    api_version = "2024-04-01"
    next_link = f"{base_url}/subscriptions/?$skipToken=123"

    # setup mock responses
    mock_response_1 = MagicMock()
    mock_response_1.json.return_value = {
        "value": [{"id": "resource1"}],
        "nextLink": next_link,
    }
    mock_response_1.headers = {}
    mock_response_1.raise_for_status.return_value = None

    mock_response_2 = MagicMock()
    mock_response_2.json.return_value = {"value": [{"id": "resource2"}]}
    mock_response_2.headers = {}
    mock_response_2.raise_for_status.return_value = None

    mock_httpx_client.request.side_effect = [mock_response_1, mock_response_2]

    client = AzureResourceManagerClient(
        credential=dummy_credential,
        base_url=base_url,
        rate_limiter=noop_rate_limiter,
    )

    monkeypatch.setattr(
        AzureResourceManagerClient,
        "client",
        PropertyMock(return_value=mock_httpx_client),
    )

    request = AzureRequest(endpoint=endpoint, data_key="value", api_version=api_version)

    results = []
    async for page in client.make_paginated_request(request):
        results.extend(page)

    assert results == [{"id": "resource1"}, {"id": "resource2"}]
    assert mock_httpx_client.request.call_count == 2


@pytest.mark.asyncio
async def test_make_paginated_request_without_nextlink(
    dummy_credential: _DummyCredential,
    noop_rate_limiter: _NoOpRateLimiter,
    mock_httpx_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = "https://management.azure.com"
    endpoint = "subscriptions/123/resources"
    api_version = "2024-04-01"

    mock_response = MagicMock()
    mock_response.json.return_value = {"value": [{"id": "resource1"}]}
    mock_response.headers = {}
    mock_response.raise_for_status.return_value = None
    mock_httpx_client.request.return_value = mock_response

    client = AzureResourceManagerClient(
        credential=dummy_credential,
        base_url=base_url,
        rate_limiter=noop_rate_limiter,
    )

    monkeypatch.setattr(
        AzureResourceManagerClient,
        "client",
        PropertyMock(return_value=mock_httpx_client),
    )

    request = AzureRequest(endpoint=endpoint, data_key="value", api_version=api_version)

    results = []
    async for page in client.make_paginated_request(request):
        results.extend(page)

    assert results == [{"id": "resource1"}]
    mock_httpx_client.request.assert_called_once()
