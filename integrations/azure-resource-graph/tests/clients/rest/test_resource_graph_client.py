import json

import pytest
from pytest_httpx import HTTPXMock

from azure_integration.clients.base import AzureRequest
from azure_integration.clients.rest.resource_graph_client import (
    AzureResourceGraphClient,
)
from tests.conftest import _DummyCredential, _NoOpRateLimiter


@pytest.mark.asyncio
async def test_make_paginated_request_with_skiptoken(
    httpx_mock: HTTPXMock,
    dummy_credential: _DummyCredential,
    noop_rate_limiter: _NoOpRateLimiter,
) -> None:
    base_url = "https://management.azure.com"
    endpoint = "resources"
    full_url = f"{base_url}/{endpoint}"
    skip_token = "skip-me"

    # Mock first page response
    httpx_mock.add_response(
        method="POST",
        url=full_url,
        json={
            "data": [{"id": "resource1"}],
            "$skipToken": skip_token,
        },
        match_content=json.dumps(
            {"query": "resources", "subscriptions": ["sub1"]}
        ).encode("utf-8"),
    )

    # Mock second page response
    httpx_mock.add_response(
        method="POST",
        url=full_url,
        json={"data": [{"id": "resource2"}]},
        match_content=json.dumps(
            {
                "query": "resources",
                "subscriptions": ["sub1"],
                "options": {"$skipToken": skip_token},
            }
        ).encode("utf-8"),
    )

    client = AzureResourceGraphClient(
        credential=dummy_credential,
        base_url=base_url,
        rate_limiter=noop_rate_limiter,
    )

    request = AzureRequest(
        endpoint=endpoint,
        data_key="data",
        json_body={"query": "resources", "subscriptions": ["sub1"]},
    )

    results = []
    async for page in client.make_paginated_request(request):
        results.extend(page)

    assert results == [{"id": "resource1"}, {"id": "resource2"}]
    requests = httpx_mock.get_requests()
    assert len(requests) == 2
    assert json.loads(requests[1].content)["options"]["$skipToken"] == skip_token


@pytest.mark.asyncio
async def test_make_paginated_request_without_skiptoken(
    httpx_mock: HTTPXMock,
    dummy_credential: _DummyCredential,
    noop_rate_limiter: _NoOpRateLimiter,
) -> None:
    base_url = "https://management.azure.com"
    endpoint = "resources"
    full_url = f"{base_url}/{endpoint}"

    # Mock response
    httpx_mock.add_response(
        method="POST",
        url=full_url,
        json={"data": [{"id": "resource1"}]},
        match_content=json.dumps(
            {"query": "resources", "subscriptions": ["sub1"]}
        ).encode("utf-8"),
    )

    client = AzureResourceGraphClient(
        credential=dummy_credential,
        base_url=base_url,
        rate_limiter=noop_rate_limiter,
    )

    request = AzureRequest(
        endpoint=endpoint,
        data_key="data",
        json_body={"query": "resources", "subscriptions": ["sub1"]},
    )

    results = []
    async for page in client.make_paginated_request(request):
        results.extend(page)

    assert results == [{"id": "resource1"}]
    requests = httpx_mock.get_requests()
    assert len(requests) == 1
