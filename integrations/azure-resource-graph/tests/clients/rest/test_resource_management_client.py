from urllib.parse import urlparse
from unittest.mock import AsyncMock

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = "https://management.azure.com"
    endpoint = "subscriptions"
    api_version = "2024-04-01"
    next_link = f"{base_url}/subscriptions/?$skipToken=123"

    mock_make_request = AsyncMock(
        side_effect=[
            {
                "value": [{"id": "resource1"}],
                "nextLink": next_link,
            },
            {"value": [{"id": "resource2"}]},
        ]
    )
    monkeypatch.setattr(AzureResourceManagerClient, "make_request", mock_make_request)

    client = AzureResourceManagerClient(
        credential=dummy_credential,
        base_url=base_url,
        rate_limiter=noop_rate_limiter,
    )

    request = AzureRequest(endpoint=endpoint, data_key="value", api_version=api_version)

    results = []
    async for page in client.make_paginated_request(request):
        results.extend(page)

    assert results == [{"id": "resource1"}, {"id": "resource2"}]
    assert mock_make_request.call_count == 2
    assert mock_make_request.call_args_list[0].args[0].endpoint == endpoint
    # This assertion highlights a bug: the client incorrectly uses only the path
    # from the absolute nextLink URL for subsequent requests.
    assert (
        mock_make_request.call_args_list[1].args[0].endpoint
        == urlparse(next_link).path.rstrip("/")
    )


@pytest.mark.asyncio
async def test_paginated_request_preserves_api_version_and_skiptoken(
    dummy_credential: _DummyCredential,
    noop_rate_limiter: _NoOpRateLimiter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = "https://management.azure.com"
    endpoint = "subscriptions"
    api_version = "2024-04-01"
    next_link = f"{base_url}/subscriptions/?$skipToken=123"

    mock_make_request = AsyncMock(
        side_effect=[
            {
                "value": [{"id": "resource1"}],
                "nextLink": next_link,
            },
            {"value": [{"id": "resource2"}]},
        ]
    )
    monkeypatch.setattr(AzureResourceManagerClient, "make_request", mock_make_request)

    client = AzureResourceManagerClient(
        credential=dummy_credential,
        base_url=base_url,
        rate_limiter=noop_rate_limiter,
    )

    request = AzureRequest(endpoint=endpoint, data_key="value", api_version=api_version)

    # Fully consume the generator to trigger all paginated calls
    results = []
    async for page in client.make_paginated_request(request):
        results.extend(page)

    assert "api-version" in mock_make_request.call_args_list[1].args[0].params
    assert (
        mock_make_request.call_args_list[1].args[0].params["api-version"] == api_version
    )
    assert "$skipToken" in mock_make_request.call_args_list[1].args[0].params


@pytest.mark.asyncio
async def test_make_paginated_request_without_nextlink(
    dummy_credential: _DummyCredential,
    noop_rate_limiter: _NoOpRateLimiter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = "https://management.azure.com"
    endpoint = "subscriptions/123/resources"
    api_version = "2024-04-01"

    mock_make_request = AsyncMock(return_value={"value": [{"id": "resource1"}]})
    monkeypatch.setattr(AzureResourceManagerClient, "make_request", mock_make_request)

    client = AzureResourceManagerClient(
        credential=dummy_credential,
        base_url=base_url,
        rate_limiter=noop_rate_limiter,
    )

    request = AzureRequest(endpoint=endpoint, data_key="value", api_version=api_version)

    results = []
    async for page in client.make_paginated_request(request):
        results.extend(page)

    assert results == [{"id": "resource1"}]
    mock_make_request.assert_called_once()
    assert mock_make_request.call_args.args[0].endpoint == endpoint
