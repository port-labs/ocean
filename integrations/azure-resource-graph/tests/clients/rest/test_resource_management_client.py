from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import pytest
from azure.core.credentials import AccessToken
from azure.core.credentials_async import AsyncTokenCredential
from pytest_httpx import HTTPXMock

from azure_integration.clients import AzureRequest
from azure_integration.clients.rest.resource_management_client import (
    AzureResourceManagerClient,
)


class _DummyCredential(AsyncTokenCredential):
    async def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        return AccessToken("dummy-token", 9999999999)


class _NoOpRateLimiter:
    @asynccontextmanager
    async def limit(self, tokens: float = 1.0) -> AsyncGenerator[None, None]:
        yield


@pytest.fixture
def dummy_credential() -> _DummyCredential:
    return _DummyCredential()


@pytest.fixture
def noop_rate_limiter() -> _NoOpRateLimiter:
    return _NoOpRateLimiter()


@pytest.mark.asyncio
async def test_make_paginated_request_with_nextlink(
    httpx_mock: HTTPXMock,
    dummy_credential: _DummyCredential,
    noop_rate_limiter: _NoOpRateLimiter,
) -> None:
    base_url = "https://management.azure.com"
    endpoint = "subscriptions/123/resources"
    next_link_path = "/next?token=123"
    first_page_url = f"{base_url}/{endpoint}"
    next_page_url = f"{base_url}{next_link_path}"

    httpx_mock.add_response(
        method="GET",
        url=first_page_url,
        json={"value": [{"id": "resource1"}], "nextLink": next_page_url},
    )
    httpx_mock.add_response(
        method="GET",
        url=next_page_url,
        json={"value": [{"id": "resource2"}]},
    )

    client = AzureResourceManagerClient(
        credential=dummy_credential,
        base_url=base_url,
        rate_limiter=noop_rate_limiter,
    )

    request = AzureRequest(endpoint=endpoint, data_key="value")

    results = []
    async for page in client.make_paginated_request(request):
        results.extend(page)

    assert results == [{"id": "resource1"}, {"id": "resource2"}]
    requests = httpx_mock.get_requests()
    assert len(requests) == 2
    assert str(requests[0].url) == first_page_url
    assert str(requests[1].url) == next_page_url


@pytest.mark.asyncio
async def test_make_paginated_request_without_nextlink(
    httpx_mock: HTTPXMock,
    dummy_credential: _DummyCredential,
    noop_rate_limiter: _NoOpRateLimiter,
) -> None:
    base_url = "https://management.azure.com"
    endpoint = "subscriptions/123/resources"
    full_url = f"{base_url}/{endpoint}"

    httpx_mock.add_response(
        method="GET", url=full_url, json={"value": [{"id": "resource1"}]}
    )

    client = AzureResourceManagerClient(
        credential=dummy_credential,
        base_url=base_url,
        rate_limiter=noop_rate_limiter,
    )

    request = AzureRequest(endpoint=endpoint, data_key="value")

    results = []
    async for page in client.make_paginated_request(request):
        results.extend(page)

    assert results == [{"id": "resource1"}]
    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    assert str(requests[0].url) == full_url
