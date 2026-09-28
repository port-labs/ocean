from typing import Any
from unittest.mock import MagicMock, patch

import httpx

from main import on_resync_tenants
from plain.client import PlainClient
from plain.queries import LIST_TENANTS
from tests.kind_helpers import collect_pages, exporter_kinds, node_selection


def test_list_tenants_query_contains_tenant_fields() -> None:
    selection = node_selection(LIST_TENANTS)

    assert "id" in selection
    assert "externalId" in selection
    assert "name" in selection
    assert "url" in selection
    assert "createdAt" in selection
    assert "updatedAt" in selection
    assert "hasNextPage" in LIST_TENANTS
    assert "endCursor" in LIST_TENANTS


def test_tenant_kind_is_registered_in_spec() -> None:
    assert "kind: tenant" in exporter_kinds()


def _client() -> PlainClient:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"api_token": "plainApiKey_test"}
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )
    with patch("plain.client.ocean", mock_ocean):
        return PlainClient(http_client=http_client)


async def test_get_tenants_yields_mocked_pages() -> None:
    client = _client()
    seen: dict[str, Any] = {}

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
    ) -> Any:
        seen["query"] = query
        seen["operation_name"] = operation_name
        seen["connection_path"] = connection_path
        yield [{"id": "te_1", "externalId": "acme", "name": "Acme"}]

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_tenants())

    assert seen["query"] is LIST_TENANTS
    assert seen["operation_name"] == "ListTenants"
    assert seen["connection_path"] == "data.tenants"
    assert batches == [[{"id": "te_1", "externalId": "acme", "name": "Acme"}]]


async def test_resync_tenants_yields_batches() -> None:
    expected = [[{"id": "te_1", "name": "Acme"}]]

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_tenants(self) -> Any:
            for batch in expected:
                yield batch

    with patch("main.PlainClient", FakeClient):
        assert on_resync_tenants is not None
        batches = await collect_pages(on_resync_tenants("tenant"))

    assert batches == expected
