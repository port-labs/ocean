from unittest.mock import AsyncMock, PropertyMock, MagicMock

import pytest

from azure_integration.clients.base import AzureRequest
from azure_integration.clients.rest.resource_graph_client import (
    AzureResourceGraphClient,
)
from tests.conftest import _DummyCredential, _NoOpRateLimiter


@pytest.mark.asyncio
async def test_make_paginated_request_with_skiptoken(
    dummy_credential: _DummyCredential,
    noop_rate_limiter: _NoOpRateLimiter,
    mock_httpx_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = "https://management.azure.com"
    endpoint = "resources"
    api_version = "2024-04-01"
    skip_token = "skip-me"

    # Mock responses
    mock_response_1 = MagicMock()
    mock_response_1.json.return_value = {
        "data": [{"id": "resource1"}],
        "$skipToken": skip_token,
        "totalRecords": 2,
        "count": 1,
    }
    mock_response_1.headers = {}
    mock_response_1.raise_for_status.return_value = None

    mock_response_2 = MagicMock()
    mock_response_2.json.return_value = {
        "data": [{"id": "resource2"}],
        "totalRecords": 2,
        "count": 1,
    }
    mock_response_2.headers = {}
    mock_response_2.raise_for_status.return_value = None

    mock_httpx_client.request.side_effect = [mock_response_1, mock_response_2]

    client = AzureResourceGraphClient(
        credential=dummy_credential,
        base_url=base_url,
        rate_limiter=noop_rate_limiter,
    )

    monkeypatch.setattr(
        AzureResourceGraphClient,
        "client",
        PropertyMock(return_value=mock_httpx_client),
    )

    request = AzureRequest(
        method="POST",
        endpoint=endpoint,
        data_key="data",
        json_body={"query": "resources", "subscriptions": ["sub1"]},
        api_version=api_version,
    )

    results = []
    async for page in client.make_paginated_request(request):
        results.extend(page)

    assert results == [{"id": "resource1"}, {"id": "resource2"}]
    assert mock_httpx_client.request.call_count == 2


@pytest.mark.asyncio
async def test_make_paginated_request_without_skiptoken(
    dummy_credential: _DummyCredential,
    noop_rate_limiter: _NoOpRateLimiter,
    mock_httpx_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = "https://management.azure.com"
    endpoint = "resources"
    api_version = "2024-04-01"

    # Mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"id": "resource1"}],
        "totalRecords": 1,
        "count": 1,
    }
    mock_response.headers = {}
    mock_response.raise_for_status.return_value = None
    mock_httpx_client.request.return_value = mock_response

    client = AzureResourceGraphClient(
        credential=dummy_credential,
        base_url=base_url,
        rate_limiter=noop_rate_limiter,
    )
    monkeypatch.setattr(
        AzureResourceGraphClient,
        "client",
        PropertyMock(return_value=mock_httpx_client),
    )

    request = AzureRequest(
        method="POST",
        endpoint=endpoint,
        data_key="data",
        json_body={"query": "resources", "subscriptions": ["sub1"]},
        api_version=api_version,
    )

    results = []
    async for page in client.make_paginated_request(request):
        results.extend(page)

    assert results == [{"id": "resource1"}]
    mock_httpx_client.request.assert_called_once()
