import asyncio

import pytest

from azure_integration.exporters.resource_graph import ResourceGraphExporter
from azure_integration.clients.base import AbstractAzureClient, AzureRequest
from azure_integration.options import ResourceGraphExporterOptions
from typing import Any, AsyncGenerator, Dict, List


class _CapturingClient(AbstractAzureClient):
    def __init__(self) -> None:
        self.requests: List[AzureRequest] = []
        self._lock = asyncio.Lock()

    async def make_request(self, request: AzureRequest) -> Dict[str, Any]:
        raise NotImplementedError

    async def make_paginated_request(
        self, request: AzureRequest
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        request_num = 0
        async with self._lock:
            self.requests.append(request)
            request_num = len(self.requests)

        yield [{"id": f"/r{request_num}-1"}]
        yield [{"id": f"/r{request_num}-2"}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subscriptions, expected_batches",
    [
        ([], 0),
        ([{"subscriptionId": "s1"}], 1),
        ([{"subscriptionId": "s1"}, {"subscriptionId": "s2"}], 1),
        ([{"subscriptionId": f"s{i}"} for i in range(100)], 1),
        ([{"subscriptionId": f"s{i}"} for i in range(101)], 2),
        ([{"subscriptionId": f"s{i}"} for i in range(250)], 3),
        ([{"subscriptionId": f"s{i}"} for i in range(1000)], 10),
        ([{"subscriptionId": f"s{i}"} for i in range(1001)], 11),
    ],
)
async def test_resource_graph_exporter_batches_subscriptions(
    subscriptions: List[Dict[str, Any]], expected_batches: int
) -> None:
    client = _CapturingClient()
    exporter = ResourceGraphExporter(client=client)

    opts = ResourceGraphExporterOptions(
        api_version="2024-04-01",
        query="Resources | project id",
        subscriptions=subscriptions,
    )

    output: List[List[Dict[str, Any]]] = []
    async for chunk in exporter.get_paginated_resources(opts):
        output.append(chunk)

    assert len(client.requests) == expected_batches
    # Each request yields twice in the mock
    assert len(output) == expected_batches * 2

    all_subscriptions_in_requests = []
    for req in client.requests:
        assert req.endpoint == "providers/Microsoft.ResourceGraph/resources"
        assert req.method == "POST"
        assert req.json_body["query"] == "Resources | project id"
        all_subscriptions_in_requests.extend(req.json_body["subscriptions"])

    assert sorted(all_subscriptions_in_requests) == sorted(
        [sub["subscriptionId"] for sub in subscriptions]
    )


@pytest.mark.asyncio
async def test_resource_graph_exporter_builds_request_and_streams() -> None:
    client = _CapturingClient()
    exporter = ResourceGraphExporter(client=client)

    opts = ResourceGraphExporterOptions(
        api_version="2024-04-01",
        query="Resources | project id",
        subscriptions=[{"subscriptionId": "s1"}, {"subscriptionId": "s2"}],
    )

    output: List[List[Dict[str, Any]]] = []
    async for chunk in exporter.get_paginated_resources(opts):
        output.append(chunk)

    assert len(client.requests) == 1
    req = client.requests[0]
    assert req.endpoint == "providers/Microsoft.ResourceGraph/resources"
    assert req.method == "POST"
    assert req.json_body == {
        "query": "Resources | project id",
        "subscriptions": ["s1", "s2"],
    }

    assert output == [[{"id": "/r1-1"}], [{"id": "/r1-2"}]]
