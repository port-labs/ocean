import pytest

from azure_integration.exporters.resource_graph import ResourceGraphExporter
from azure_integration.clients.base import AbstractAzureClient, AzureRequest
from azure_integration.options import ResourceGraphExporterOptions
from typing import Any, AsyncGenerator, Dict, List


class _CapturingClient(AbstractAzureClient):
    def __init__(self) -> None:
        self.last_request: AzureRequest | None = None

    async def make_request(self, request: AzureRequest) -> Dict[str, Any]:
        raise NotImplementedError

    async def make_paginated_request(
        self, request: AzureRequest
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        self.last_request = request
        yield [{"id": "/r1"}]
        yield [{"id": "/r2"}]


@pytest.mark.asyncio
async def test_resource_graph_exporter_builds_request_and_streams() -> None:
    client = _CapturingClient()
    exporter = ResourceGraphExporter(client=client)

    opts = ResourceGraphExporterOptions(
        api_version="2024-04-01",
        query="Resources | project id",
        subscriptions=["s1", "s2"],
    )

    output: List[List[Dict[str, Any]]] = []
    async for chunk in exporter.get_paginated_resources(opts):
        output.append(chunk)

    assert client.last_request is not None
    req = client.last_request
    assert req.endpoint == "providers/Microsoft.ResourceGraph/resources"
    assert req.method == "POST"
    assert req.api_version == "2024-04-01"
    assert req.data_key == "data"
    assert req.json_body == {
        "query": "Resources | project id",
        "subscriptions": ["s1", "s2"],
    }

    assert output == [[{"id": "/r1"}], [{"id": "/r2"}]]
