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
from plain.queries import LIST_THREAD_IDS, THREAD_TIMELINE
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


def test_thread_message_kind_is_registered_in_spec() -> None:
    assert "kind: thread-message" in exporter_kinds()


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

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        seen["statuses"] = statuses
        yield [{"id": "th_1"}]

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
                "id": "tl_1",
                "threadId": "th_1",
                "llmText": "Hello",
                "entry": {"__typename": "ChatEntry"},
            },
            {
                "id": "tl_2",
                "threadId": "th_1",
                "llmText": None,
                "entry": {"__typename": "ThreadStatusTransitionedEntry"},
            },
            {
                "id": "tl_3",
                "threadId": "th_1",
                "llmText": "   ",
                "entry": {"__typename": "NoteEntry"},
            },
        ]

    client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_thread_messages([]))

    assert seen["statuses"] == []
    assert seen["query"] is THREAD_TIMELINE
    assert seen["operation_name"] == "ThreadTimeline"
    assert seen["variables"] == {"threadId": "th_1"}
    assert seen["connection_path"] == "thread.timelineEntries"
    assert [entry["id"] for entry in batches[0]] == ["tl_1"]


async def test_get_thread_messages_raises_when_thread_is_missing() -> None:
    client = make_client()

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        yield [{"id": "th_missing"}]

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
    ) -> Any:
        raise PlainGraphQLError(
            [
                {
                    "message": (
                        "Plain response is missing connection 'thread.timelineEntries'"
                    )
                }
            ]
        )
        yield []

    client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]

    with pytest.raises(
        PlainGraphQLError, match="Plain thread 'th_missing' was not found"
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
