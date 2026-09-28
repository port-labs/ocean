from typing import Any
from unittest.mock import patch

import httpx

from main import on_resync_threads
from plain.queries import LIST_THREADS
from tests.kind_helpers import (
    collect_pages,
    exporter_kinds,
    make_client,
    node_selection,
)


def test_list_threads_query_includes_relations_labels_and_fields() -> None:
    selection = node_selection(LIST_THREADS)

    assert "customer" in selection
    assert "tenant" in selection
    assert "assignedTo" in selection
    assert "__typename" in selection
    assert "... on User" in selection
    assert "labels" in selection
    assert "threadFields" in selection
    assert "filters: $filters" in LIST_THREADS
    assert "hasNextPage" in LIST_THREADS


def test_thread_kind_is_registered_in_spec() -> None:
    assert "kind: thread" in exporter_kinds()


async def test_get_threads_yields_pages_with_assignee_typename() -> None:
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
        seen["variables"] = variables
        seen["connection_path"] = connection_path
        yield [
            {
                "id": "th_1",
                "title": "Login help",
                "assignedTo": {"__typename": "User", "id": "us_1"},
            }
        ]

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_threads())

    assert seen["query"] is LIST_THREADS
    assert seen["operation_name"] == "ListThreads"
    assert seen["connection_path"] == "data.threads"
    assert seen["variables"] is None
    assert batches[0][0]["assignedTo"]["__typename"] == "User"


async def test_get_threads_passes_status_filter() -> None:
    client = make_client({"thread_status_filter": "TODO, DONE"})
    seen: dict[str, Any] = {}

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
    ) -> Any:
        seen["variables"] = variables
        yield []

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    await collect_pages(client.get_threads())

    assert seen["variables"] == {"filters": {"statuses": ["TODO", "DONE"]}}


async def test_resync_threads_yields_batches() -> None:
    expected = [
        [
            {
                "id": "th_1",
                "assignedTo": {"__typename": "MachineUser", "id": "mu_1"},
            }
        ]
    ]

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_threads(self) -> Any:
            for batch in expected:
                yield batch

    with patch("main.PlainClient", FakeClient):
        assert on_resync_threads is not None
        batches = await collect_pages(on_resync_threads("thread"))

    assert batches == expected
    assert batches[0][0]["assignedTo"]["__typename"] == "MachineUser"
