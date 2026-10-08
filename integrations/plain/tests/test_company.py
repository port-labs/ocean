from typing import Any
from unittest.mock import MagicMock, patch

import httpx

from main import on_resync_companies
from plain.client import PlainClient
from plain.queries import LIST_COMPANIES
from tests.kind_helpers import collect_pages, exporter_kinds, node_selection


def test_list_companies_query_contains_company_fields() -> None:
    selection = node_selection(LIST_COMPANIES)

    assert "id" in selection
    assert "name" in selection
    assert "domainName" in selection
    assert "createdAt" in selection
    assert "updatedAt" in selection
    assert "iso8601" in LIST_COMPANIES
    assert "hasNextPage" in LIST_COMPANIES
    assert "endCursor" in LIST_COMPANIES
    # Company has no externalId in the Plain schema.
    assert "externalId" not in LIST_COMPANIES


def test_company_kind_is_registered_in_spec() -> None:
    assert "kind: company" in exporter_kinds()


def _client() -> PlainClient:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"api_token": "plainApiKey_test"}
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )
    with patch("plain.client.ocean", mock_ocean):
        return PlainClient(http_client=http_client)


async def test_get_companies_yields_mocked_pages() -> None:
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
        yield [{"id": "co_1", "name": "Acme", "domainName": "acme.com"}]
        yield [{"id": "co_2", "name": "Beta", "domainName": "beta.com"}]

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_companies())

    assert seen["query"] is LIST_COMPANIES
    assert seen["operation_name"] == "ListCompanies"
    assert seen["connection_path"] == "data.companies"
    assert batches == [
        [{"id": "co_1", "name": "Acme", "domainName": "acme.com"}],
        [{"id": "co_2", "name": "Beta", "domainName": "beta.com"}],
    ]


async def test_resync_companies_yields_batches() -> None:
    expected = [[{"id": "co_1", "name": "Acme"}]]

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_companies(self) -> Any:
            for batch in expected:
                yield batch

    with patch("main.PlainClient", FakeClient):
        assert on_resync_companies is not None
        batches = await collect_pages(on_resync_companies("company"))

    assert batches == expected
