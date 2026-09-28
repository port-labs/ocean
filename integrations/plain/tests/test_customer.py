from typing import Any

from main import on_resync_customers
from plain.queries import LIST_CUSTOMERS
from tests.kind_helpers import (
    collect_pages,
    exporter_kinds,
    make_client,
    node_selection,
)


def test_list_customers_query_includes_relation_ids() -> None:
    selection = node_selection(LIST_CUSTOMERS)

    assert "id" in selection
    assert "externalId" in selection
    assert "fullName" in selection
    assert "email" in selection
    assert "company" in selection
    assert "tenantMemberships" in selection
    assert "tenant" in selection
    assert "hasNextPage" in LIST_CUSTOMERS
    assert "endCursor" in LIST_CUSTOMERS


def test_customer_kind_is_registered_in_spec() -> None:
    assert "kind: customer" in exporter_kinds()


async def test_get_customers_yields_mocked_pages() -> None:
    client = make_client()
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
        yield [
            {
                "id": "c_1",
                "fullName": "Ada Lovelace",
                "company": {"id": "co_1"},
                "tenantMemberships": {"edges": [{"node": {"tenant": {"id": "te_1"}}}]},
            }
        ]

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_customers())

    assert seen["query"] is LIST_CUSTOMERS
    assert seen["operation_name"] == "ListCustomers"
    assert seen["connection_path"] == "data.customers"
    assert batches[0][0]["company"]["id"] == "co_1"
    assert batches[0][0]["tenantMemberships"]["edges"][0]["node"]["tenant"]["id"] == (
        "te_1"
    )


async def test_resync_customers_yields_batches() -> None:
    from unittest.mock import patch

    import httpx

    expected = [[{"id": "c_1", "fullName": "Ada Lovelace"}]]

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_customers(self) -> Any:
            for batch in expected:
                yield batch

    with patch("main.PlainClient", FakeClient):
        assert on_resync_customers is not None
        batches = await collect_pages(on_resync_customers("customer"))

    assert batches == expected
