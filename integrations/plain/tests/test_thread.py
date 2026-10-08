from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import httpx
from port_ocean.context.resource import resource_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from integration import ThreadResourceConfig
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
    assert "tier" in selection
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


def _thread_resource(exclude_done_threads: bool) -> ThreadResourceConfig:
    config = ThreadResourceConfig.parse_obj(
        {
            "kind": "thread",
            "selector": {
                "query": "true",
                "excludeDoneThreads": exclude_done_threads,
            },
            "port": {
                "entity": {
                    "mappings": {
                        "identifier": ".id",
                        "blueprint": '"plainThread"',
                    }
                }
            },
        }
    )
    assert isinstance(config, ThreadResourceConfig)
    return config


async def test_resync_threads_yields_batches() -> None:
    expected = [
        [
            {
                "id": "th_1",
                "assignedTo": {"__typename": "MachineUser", "id": "mu_1"},
            }
        ]
    ]
    seen: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_threads(self, statuses: list[str] | None = None) -> Any:
            seen["statuses"] = statuses
            for batch in expected:
                yield batch

    with patch("main.PlainClient", FakeClient):
        assert on_resync_threads is not None
        async with resource_context(_thread_resource(False)):
            batches = await collect_pages(on_resync_threads("thread"))

    assert batches == expected
    assert seen["statuses"] is None
    assert batches[0][0]["assignedTo"]["__typename"] == "MachineUser"


async def test_resync_threads_honors_thread_status_filter_when_exclude_done_is_false() -> (
    None
):
    seen: dict[str, Any] = {}

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
    ) -> Any:
        seen["variables"] = variables
        yield []

    client = make_client({"thread_status_filter": "TODO, SNOOZED"})
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]

    with patch("main.PlainClient", return_value=client):
        assert on_resync_threads is not None
        async with resource_context(_thread_resource(False)):
            await collect_pages(on_resync_threads("thread"))

    assert seen["variables"] == {"filters": {"statuses": ["TODO", "SNOOZED"]}}


async def test_resync_threads_excludes_done_when_mapping_flag_is_set() -> None:
    seen: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_threads(self, statuses: list[str] | None = None) -> Any:
            seen["statuses"] = statuses
            yield []

    with patch("main.PlainClient", FakeClient):
        assert on_resync_threads is not None
        async with resource_context(_thread_resource(True)):
            await collect_pages(on_resync_threads("thread"))

    assert seen["statuses"] == ["TODO", "SNOOZED"]


async def test_resync_threads_reads_exclude_flag_without_local_config_class() -> None:
    seen: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_threads(self, statuses: list[str] | None = None) -> Any:
            seen["statuses"] = statuses
            yield []

    # Ocean parses the mapping with a second copy of integration.py, so the
    # live object is not this module's ThreadResourceConfig.
    config = cast(
        ResourceConfig,
        SimpleNamespace(
            kind="thread",
            selector=SimpleNamespace(exclude_done_threads=True),
        ),
    )
    assert not isinstance(config, ThreadResourceConfig)

    with patch("main.PlainClient", FakeClient):
        assert on_resync_threads is not None
        async with resource_context(config):
            await collect_pages(on_resync_threads("thread"))

    assert seen["statuses"] == ["TODO", "SNOOZED"]
