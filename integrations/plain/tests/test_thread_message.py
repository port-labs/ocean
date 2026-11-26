from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import httpx
import pytest
from port_ocean.context.resource import resource_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from integration import ThreadMessageResourceConfig
from main import on_resync_thread_messages
from plain.exceptions import PlainGraphQLError
from plain.queries import LIST_THREAD_IDS, LIST_THREAD_TIMELINES, THREAD_TIMELINE
from tests.kind_helpers import (
    collect_pages,
    exporter_kinds,
    make_client,
)
from tests.test_port_app_config import _apply, _load_json, _mappings


def test_thread_timeline_query_selects_message_fields() -> None:
    assert "llmText" in THREAD_TIMELINE
    assert "threadId" in THREAD_TIMELINE
    assert "entry {" in THREAD_TIMELINE
    assert "__typename" in THREAD_TIMELINE
    assert "timelineEntries" in THREAD_TIMELINE
    assert "filters: $filters" in LIST_THREAD_IDS
    assert "llmText" in LIST_THREAD_TIMELINES
    assert "threads(first:" in LIST_THREAD_TIMELINES
    assert "timelineEntries(first: $timelineFirst)" in LIST_THREAD_TIMELINES


def test_thread_message_kind_is_registered_in_spec() -> None:
    assert "thread-message" in exporter_kinds()


def test_thread_message_mapping_resolves_identifier_and_thread() -> None:
    message = _load_json(Path("tests/fixtures/thread_message.json"))
    mappings = _mappings()["thread-message"]

    assert _apply(mappings["identifier"], message) == "tl_1"
    assert _apply(mappings["relations"]["thread"], message) == "th_1"
    assert _apply(mappings["properties"]["text"], message) == "Hello from the customer"
    assert _apply(mappings["properties"]["entryType"], message) == "ChatEntry"
    assert _apply(mappings["properties"]["actorId"], message) == "c_1"
    assert _apply(mappings["title"], message) == "ChatEntry: Hello from the customer"


async def test_get_thread_messages_skips_entries_without_text() -> None:
    client = make_client()
    seen: dict[str, Any] = {}

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        seen["query"] = query
        seen["operation_name"] = operation_name
        seen["variables"] = variables
        seen["connection_path"] = connection_path
        seen["after"] = after
        yield [
            {
                "id": "th_1",
                "timelineEntries": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "edges": [
                        {
                            "node": {
                                "id": "tl_1",
                                "threadId": "th_1",
                                "llmText": "Hello",
                                "entry": {"__typename": "ChatEntry"},
                            }
                        },
                        {
                            "node": {
                                "id": "tl_2",
                                "threadId": "th_1",
                                "llmText": None,
                                "entry": {
                                    "__typename": "ThreadStatusTransitionedEntry"
                                },
                            }
                        },
                        {
                            "node": {
                                "id": "tl_3",
                                "threadId": "th_1",
                                "llmText": "   ",
                                "entry": {"__typename": "NoteEntry"},
                            }
                        },
                    ],
                },
            }
        ]

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_thread_messages([]))

    assert seen["variables"]["filters"]["statuses"] == []
    assert seen["query"] is LIST_THREAD_TIMELINES
    assert seen["operation_name"] == "ListThreadTimelines"
    assert seen["connection_path"] == "data.threads"
    assert seen["after"] is None
    assert [entry["id"] for entry in batches[0]] == ["tl_1"]


async def test_get_thread_messages_raises_when_thread_is_missing_timeline() -> None:
    client = make_client()

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        yield [
            {
                "id": "th_missing",
                "timelineEntries": None,
            }
        ]

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]

    with pytest.raises(
        PlainGraphQLError, match="Plain thread 'th_missing' missing timelineEntries"
    ):
        await collect_pages(client.get_thread_messages([]))


def _message_resource(exclude_done_threads: bool) -> ThreadMessageResourceConfig:
    config = ThreadMessageResourceConfig.parse_obj(
        {
            "kind": "thread-message",
            "selector": {
                "query": "true",
                "excludeDoneThreads": exclude_done_threads,
            },
            "port": {
                "entity": {
                    "mappings": {
                        "identifier": ".id",
                        "blueprint": '"plainThreadMessage"',
                    }
                }
            },
        }
    )
    assert isinstance(config, ThreadMessageResourceConfig)
    return config


async def test_resync_thread_messages_excludes_done_threads_when_flag_is_set() -> None:
    seen: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_thread_messages(self, statuses: list[str] | None = None) -> Any:
            seen["statuses"] = statuses
            yield [{"id": "tl_1", "threadId": "th_1", "llmText": "Hello"}]

    with patch("main.PlainClient", FakeClient):
        assert on_resync_thread_messages is not None
        async with resource_context(_message_resource(True)):
            batches = await collect_pages(on_resync_thread_messages("thread-message"))

    assert seen["statuses"] == ["TODO", "SNOOZED"]
    assert batches[0][0]["id"] == "tl_1"


async def test_resync_thread_messages_requests_every_status_when_flag_is_false() -> (
    None
):
    seen: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_thread_messages(self, statuses: list[str] | None = None) -> Any:
            seen["statuses"] = statuses
            yield []

    with patch("main.PlainClient", FakeClient):
        assert on_resync_thread_messages is not None
        async with resource_context(_message_resource(False)):
            await collect_pages(on_resync_thread_messages("thread-message"))

    assert seen["statuses"] is None


async def test_resync_thread_messages_reads_exclude_flag_without_local_config_class() -> (
    None
):
    seen: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_thread_messages(self, statuses: list[str] | None = None) -> Any:
            seen["statuses"] = statuses
            yield []

    config = cast(
        ResourceConfig,
        SimpleNamespace(
            kind="thread-message",
            selector=SimpleNamespace(exclude_done_threads=True),
        ),
    )
    assert not isinstance(config, ThreadMessageResourceConfig)

    with patch("main.PlainClient", FakeClient):
        assert on_resync_thread_messages is not None
        async with resource_context(config):
            await collect_pages(on_resync_thread_messages("thread-message"))

    assert seen["statuses"] == ["TODO", "SNOOZED"]


async def test_get_thread_messages_batches_threads_by_page_size() -> None:
    """With 250 threads and pageSize 100, paginate_connection yields 3 pages."""
    client = make_client()
    page_count = 0

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        nonlocal page_count
        # Simulate 3 pages of 100, 100, 50 threads
        yield [
            {
                "id": f"th_{i}",
                "timelineEntries": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "edges": [],
                },
            }
            for i in range(100)
        ]
        page_count += 1
        yield [
            {
                "id": f"th_{i}",
                "timelineEntries": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "edges": [],
                },
            }
            for i in range(100, 200)
        ]
        page_count += 1
        yield [
            {
                "id": f"th_{i}",
                "timelineEntries": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "edges": [],
                },
            }
            for i in range(200, 250)
        ]
        page_count += 1

    async with resource_context(_message_resource(False)):
        client.paginate_connection = paginate_connection  # type: ignore[method-assign]
        await collect_pages(client.get_thread_messages(None))

    assert page_count == 3


async def test_get_thread_messages_follows_nested_pagination() -> None:
    """When nested hasNextPage is true, follows up with endCursor."""
    client = make_client()
    seen_operations: list[tuple[str, dict[str, Any] | None]] = []

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        seen_operations.append((operation_name, variables))
        if operation_name == "ListThreadTimelines":
            yield [
                {
                    "id": "th_1",
                    "timelineEntries": {
                        "pageInfo": {
                            "hasNextPage": True,
                            "endCursor": "cursor-nested-1",
                        },
                        "edges": [
                            {
                                "node": {
                                    "id": "tl_1",
                                    "threadId": "th_1",
                                    "llmText": "First",
                                    "entry": {"__typename": "ChatEntry"},
                                }
                            }
                        ],
                    },
                }
            ]
        else:
            yield [
                {
                    "id": "tl_2",
                    "threadId": "th_1",
                    "llmText": "Second",
                    "entry": {"__typename": "ChatEntry"},
                }
            ]

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_thread_messages(None))

    assert len(seen_operations) == 2
    assert seen_operations[0][0] == "ListThreadTimelines"
    assert seen_operations[1][0] == "ThreadTimeline"
    assert seen_operations[1][1] == {"threadId": "th_1"}
    assert len(batches) == 2
    assert batches[0][0]["id"] == "tl_1"
    assert batches[1][0]["id"] == "tl_2"


async def test_get_thread_messages_raises_on_nested_has_next_without_cursor() -> None:
    """When nested hasNextPage is true but endCursor is missing, raises."""
    client = make_client()

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        yield [
            {
                "id": "th_1",
                "timelineEntries": {
                    "pageInfo": {"hasNextPage": True, "endCursor": None},
                    "edges": [],
                },
            }
        ]

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]

    with pytest.raises(
        PlainGraphQLError,
        match="Plain thread 'th_1' reported nested hasNextPage without endCursor",
    ):
        await collect_pages(client.get_thread_messages(None))


async def test_get_thread_messages_passes_exclude_done_statuses() -> None:
    """excludeDoneThreads passes correct ThreadsFilter."""
    client = make_client()
    seen_variables: dict[str, Any] = {}

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        seen_variables.update(variables or {})
        yield []

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    async with resource_context(_message_resource(True)):
        await collect_pages(client.get_thread_messages(["TODO", "SNOOZED"]))

    assert seen_variables["filters"]["statuses"] == ["TODO", "SNOOZED"]


async def test_get_thread_messages_parity_with_old_implementation() -> None:
    """New batched implementation yields same entries as old per-thread approach."""
    client = make_client()

    # Fixture: 3 threads with various timeline entries
    fixture_threads = [
        {
            "id": "th_1",
            "timelineEntries": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "edges": [
                    {
                        "node": {
                            "id": "tl_1_1",
                            "threadId": "th_1",
                            "llmText": "Message 1",
                            "entry": {"__typename": "ChatEntry"},
                        }
                    },
                    {
                        "node": {
                            "id": "tl_1_2",
                            "threadId": "th_1",
                            "llmText": "",
                            "entry": {"__typename": "StatusEntry"},
                        }
                    },
                ],
            },
        },
        {
            "id": "th_2",
            "timelineEntries": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "edges": [
                    {
                        "node": {
                            "id": "tl_2_1",
                            "threadId": "th_2",
                            "llmText": "Message 2",
                            "entry": {"__typename": "EmailEntry"},
                        }
                    }
                ],
            },
        },
        {
            "id": "th_3",
            "timelineEntries": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "edges": [],
            },
        },
    ]

    # Simulate old per-thread implementation
    old_results: list[dict[str, Any]] = []
    for thread in fixture_threads:
        timeline_conn = thread.get("timelineEntries")
        if isinstance(timeline_conn, dict):
            edges = timeline_conn.get("edges", [])
            for edge in edges:
                if isinstance(edge, dict):
                    node = edge.get("node")
                    if isinstance(node, dict):
                        text = node.get("llmText")
                        if isinstance(text, str) and text.strip():
                            old_results.append(node)

    # Simulate new batched implementation
    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        yield fixture_threads

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    new_batches = await collect_pages(client.get_thread_messages(None))
    new_results = [entry for batch in new_batches for entry in batch]

    # Verify parity: same IDs in same order
    assert len(old_results) == len(new_results)
    assert [e["id"] for e in old_results] == [e["id"] for e in new_results]
    # Verify llmText filter worked
    assert all(e["llmText"].strip() for e in new_results)
    # Verify threadId is present
    assert all("threadId" in e for e in new_results)
