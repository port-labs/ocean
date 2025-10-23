import pytest

from azure_integration.exporters.subscription import SubscriptionExporter
from azure_integration.clients.base import AbstractAzureClient, AzureRequest
from typing import Any, AsyncGenerator, Dict, List


class _FakeClient(AbstractAzureClient):
    def __init__(self) -> None:  # noqa: D401
        pass

    async def make_request(self, request: AzureRequest) -> Dict[str, Any]:
        raise NotImplementedError

    async def make_paginated_request(
        self, request: AzureRequest
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [{"subscriptionId": "sub-1"}, {"subscriptionId": "sub-2"}]


@pytest.mark.asyncio
async def test_subscription_exporter_streams_subscriptions() -> None:
    exporter = SubscriptionExporter(client=_FakeClient())

    results: List[List[Dict[str, Any]]] = []
    async for chunk in exporter.get_paginated_resources():
        results.append(chunk)

    assert results == [[{"subscriptionId": "sub-1"}, {"subscriptionId": "sub-2"}]]
