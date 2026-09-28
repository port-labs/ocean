from typing import Any
from unittest.mock import MagicMock, patch

import httpx

from main import on_resync_users
from plain.client import PlainClient
from plain.queries import LIST_USERS
from tests.kind_helpers import collect_pages, exporter_kinds, node_selection


def test_list_users_query_contains_user_fields() -> None:
    selection = node_selection(LIST_USERS)

    assert "id" in selection
    assert "fullName" in selection
    assert "email" in selection
    assert "status" in selection
    assert "role" in selection
    assert "hasNextPage" in LIST_USERS
    assert "endCursor" in LIST_USERS


def test_user_kind_is_registered_in_spec() -> None:
    assert "kind: user" in exporter_kinds()


def _client() -> PlainClient:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"api_token": "plainApiKey_test"}
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )
    with patch("plain.client.ocean", mock_ocean):
        return PlainClient(http_client=http_client)


async def test_get_users_yields_mocked_pages() -> None:
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
        yield [{"id": "us_1", "fullName": "Ada Lovelace", "email": "ada@example.com"}]

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_users())

    assert seen["query"] is LIST_USERS
    assert seen["operation_name"] == "ListUsers"
    assert seen["connection_path"] == "data.users"
    assert batches == [
        [{"id": "us_1", "fullName": "Ada Lovelace", "email": "ada@example.com"}]
    ]


async def test_resync_users_yields_batches() -> None:
    expected = [[{"id": "us_1", "fullName": "Ada Lovelace"}]]

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_users(self) -> Any:
            for batch in expected:
                yield batch

    with patch("main.PlainClient", FakeClient):
        assert on_resync_users is not None
        batches = await collect_pages(on_resync_users("user"))

    assert batches == expected
