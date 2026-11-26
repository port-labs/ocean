from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import httpx
import pytest
from port_ocean.context.resource import resource_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from integration import DiscussionMessageResourceConfig, DiscussionResourceConfig
from main import on_resync_discussion_messages, on_resync_discussions
from plain.exceptions import PlainGraphQLError
from plain.queries import (
    DISCUSSION_MESSAGES,
    THREAD_DISCUSSION_IDS,
    THREAD_DISCUSSIONS,
)
from tests.kind_helpers import collect_pages, exporter_kinds, make_client
from tests.test_port_app_config import _apply, _load_json, _mappings


def test_discussion_queries_select_channel_and_message_fields() -> None:
    assert "threadIds: $threadIds" in THREAD_DISCUSSIONS
    assert "$threadIds: [ID!]!" in THREAD_DISCUSSIONS
    assert "sortBy: { field: CREATED_AT, direction: ASC }" in THREAD_DISCUSSIONS
    assert "slackMessageLink" in THREAD_DISCUSSIONS
    assert "emailRecipients" in THREAD_DISCUSSIONS
    assert "userId" in THREAD_DISCUSSIONS
    assert "threadIds: $threadIds" in THREAD_DISCUSSION_IDS
    assert "$threadIds: [ID!]!" in THREAD_DISCUSSION_IDS
    assert "sortBy: { field: CREATED_AT, direction: ASC }" in THREAD_DISCUSSION_IDS
    assert "threadId" in THREAD_DISCUSSION_IDS
    assert "channelDetails" in THREAD_DISCUSSION_IDS
    assert "__typename" in THREAD_DISCUSSION_IDS
    assert "discussion(discussionId: $discussionId)" in DISCUSSION_MESSAGES
    assert "slackMessageLink" in DISCUSSION_MESSAGES


def test_discussion_kinds_are_registered_in_spec() -> None:
    kinds = exporter_kinds()
    assert "discussion" in kinds
    assert "discussion-message" in kinds


def test_discussion_mapping_keeps_slack_and_email_fields_when_present() -> None:
    mappings = _mappings()["discussion"]
    slack = _load_json(Path("tests/fixtures/discussion_slack.json"))
    email = _load_json(Path("tests/fixtures/discussion_email.json"))

    assert _apply(mappings["identifier"], slack) == "disc_1"
    assert _apply(mappings["title"], slack) == "Check the refund"
    assert _apply(mappings["relations"]["thread"], slack) == "th_1"
    assert _apply(mappings["properties"]["channel"], slack) == "SLACK"
    assert _apply(mappings["properties"]["slackChannelName"], slack) == "support"
    assert (
        _apply(mappings["properties"]["slackMessageLink"], slack)
        == "slack://channel?team=T1&id=C1&message=1"
    )
    assert _apply(mappings["properties"]["emailRecipients"], slack) is None
    assert _apply(mappings["properties"]["createdById"], slack) == "u_1"

    assert _apply(mappings["properties"]["channel"], email) == "EMAIL"
    assert _apply(mappings["properties"]["slackMessageLink"], email) is None
    assert _apply(mappings["properties"]["emailRecipients"], email) == [
        "a@example.com",
        "b@example.com",
    ]
    assert _apply(mappings["properties"]["createdById"], email) == "mu_1"
    assert _apply(mappings["properties"]["resolvedAt"], email) == "2026-02-03T00:00:00Z"


def test_discussion_message_mapping_relates_thread_and_discussion() -> None:
    message = _load_json(Path("tests/fixtures/discussion_message.json"))
    mappings = _mappings()["discussion-message"]

    assert _apply(mappings["identifier"], message) == "dm_1"
    assert _apply(mappings["relations"]["thread"], message) == "th_1"
    assert _apply(mappings["relations"]["discussion"], message) == "disc_1"
    assert (
        _apply(mappings["properties"]["text"], message) == "Looking into the refund now"
    )
    assert _apply(mappings["properties"]["messageType"], message) == "OUTBOUND"
    assert (
        _apply(mappings["properties"]["slackMessageLink"], message)
        == "slack://channel?team=T1&id=C1&message=2"
    )
    assert _apply(mappings["properties"]["authorId"], message) == "u_1"
    assert _apply(mappings["title"], message) == "OUTBOUND: Looking into the refund now"


async def test_get_discussions_batches_threads() -> None:
    client = make_client()
    seen: dict[str, Any] = {}

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        seen["statuses"] = statuses
        yield [{"id": "th_1"}, {"id": "th_2"}, {"id": ""}]

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
        yield [
            {"id": "disc_1", "threadId": "th_1", "title": "Check the refund"},
            {"id": "disc_2", "threadId": "th_2", "title": "Another thread"},
        ]

    client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_discussions(["TODO", "SNOOZED"]))

    assert seen["statuses"] == ["TODO", "SNOOZED"]
    assert seen["query"] is THREAD_DISCUSSIONS
    assert seen["operation_name"] == "ThreadDiscussions"
    assert seen["variables"] == {"threadIds": ["th_1", "th_2"]}
    assert seen["connection_path"] == "discussions"
    assert len(batches[0]) == 2
    assert batches[0][0]["id"] == "disc_1"
    assert batches[0][1]["id"] == "disc_2"


async def test_get_discussions_skips_ai_channels_when_requested() -> None:
    client = make_client()

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        yield [{"id": "th_1"}]

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
                "id": "disc_slack",
                "threadId": "th_1",
                "channelDetails": {"__typename": "ThreadDiscussionSlackChannelDetails"},
            },
            {
                "id": "disc_agent",
                "threadId": "th_1",
                "channelDetails": {
                    "__typename": "ThreadDiscussionAgentSessionChannelDetails"
                },
            },
            {
                "id": "disc_cursor",
                "threadId": "th_1",
                "channelDetails": {
                    "__typename": (
                        "ThreadDiscussionCursorWorkspaceBackgroundAgentChannelDetails"
                    )
                },
            },
        ]

    client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(
        client.get_discussions([], exclude_ai_discussions=True)
    )

    assert [discussion["id"] for discussion in batches[0]] == ["disc_slack"]


async def test_get_discussion_messages_stamps_parent_thread_id() -> None:
    client = make_client()
    seen: list[dict[str, Any]] = []

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        yield [{"id": "th_1"}]

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        seen.append(
            {
                "query": query,
                "operation_name": operation_name,
                "variables": variables,
                "connection_path": connection_path,
            }
        )
        if operation_name == "ThreadDiscussionIds":
            yield [{"id": "disc_1", "threadId": "th_1"}]
            return
        yield [
            {
                "id": "dm_1",
                "threadDiscussionId": "disc_1",
                "text": "Looking into the refund now",
                "slackMessageLink": None,
            }
        ]

    client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_discussion_messages([]))

    assert seen[0]["query"] is THREAD_DISCUSSION_IDS
    assert seen[0]["variables"] == {"threadIds": ["th_1"]}
    assert seen[0]["connection_path"] == "discussions"
    assert seen[1]["query"] is DISCUSSION_MESSAGES
    assert seen[1]["variables"] == {"discussionId": "disc_1"}
    assert seen[1]["connection_path"] == "discussion.messages"
    assert batches[0][0]["threadId"] == "th_1"
    assert batches[0][0]["threadDiscussionId"] == "disc_1"


async def test_get_discussion_messages_skips_ai_discussions_when_requested() -> None:
    client = make_client()
    fetched_ids: list[str] = []

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        yield [{"id": "th_1"}]

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        if operation_name == "ThreadDiscussionIds":
            yield [
                {
                    "id": "disc_human",
                    "threadId": "th_1",
                    "channelDetails": {
                        "__typename": "ThreadDiscussionSlackChannelDetails"
                    },
                },
                {
                    "id": "disc_agent",
                    "threadId": "th_1",
                    "channelDetails": {
                        "__typename": "ThreadDiscussionAgentSessionChannelDetails"
                    },
                },
            ]
            return
        assert variables is not None
        discussion_id = str(variables["discussionId"])
        fetched_ids.append(discussion_id)
        yield [{"id": "dm_1", "threadDiscussionId": discussion_id}]

    client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(
        client.get_discussion_messages([], exclude_ai_discussions=True)
    )

    assert fetched_ids == ["disc_human"]
    assert batches[0][0]["threadDiscussionId"] == "disc_human"


async def test_get_discussion_messages_raises_when_discussion_is_missing() -> None:
    client = make_client()

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        yield [{"id": "th_1"}]

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        if operation_name == "ThreadDiscussionIds":
            yield [{"id": "disc_missing", "threadId": "th_1"}]
            return
        raise PlainGraphQLError(
            [
                {
                    "message": (
                        "Plain response is missing connection 'discussion.messages'"
                    )
                }
            ]
        )
        yield []

    client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]

    with pytest.raises(
        PlainGraphQLError, match="Plain discussion 'disc_missing' was not found"
    ):
        await collect_pages(client.get_discussion_messages([]))


def _resource(
    kind: str,
    exclude_done_threads: bool,
    *,
    exclude_ai_discussions: bool = False,
) -> ResourceConfig:
    blueprint = (
        '"plainDiscussion"' if kind == "discussion" else '"plainDiscussionMessage"'
    )
    config_cls = (
        DiscussionResourceConfig
        if kind == "discussion"
        else DiscussionMessageResourceConfig
    )
    config = config_cls.parse_obj(
        {
            "kind": kind,
            "selector": {
                "query": "true",
                "excludeDoneThreads": exclude_done_threads,
                "excludeAiDiscussions": exclude_ai_discussions,
            },
            "port": {
                "entity": {
                    "mappings": {
                        "identifier": ".id",
                        "blueprint": blueprint,
                    }
                }
            },
        }
    )
    assert isinstance(config, config_cls)
    return config


@pytest.mark.parametrize(
    ("handler", "kind"),
    [
        (on_resync_discussions, "discussion"),
        (on_resync_discussion_messages, "discussion-message"),
    ],
)
async def test_resync_passes_open_statuses_when_flag_is_set(
    handler: Any, kind: str
) -> None:
    seen: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_discussions(
            self,
            statuses: list[str] | None = None,
            *,
            exclude_ai_discussions: bool = False,
        ) -> Any:
            seen["statuses"] = statuses
            seen["exclude_ai_discussions"] = exclude_ai_discussions
            yield [{"id": "disc_1"}]

        async def get_discussion_messages(
            self,
            statuses: list[str] | None = None,
            *,
            exclude_ai_discussions: bool = False,
        ) -> Any:
            seen["statuses"] = statuses
            seen["exclude_ai_discussions"] = exclude_ai_discussions
            yield [{"id": "dm_1", "threadId": "th_1"}]

    with patch("main.PlainClient", FakeClient):
        assert handler is not None
        async with resource_context(_resource(kind, True)):
            await collect_pages(handler(kind))

    assert seen["statuses"] == ["TODO", "SNOOZED"]


@pytest.mark.parametrize(
    ("handler", "kind"),
    [
        (on_resync_discussions, "discussion"),
        (on_resync_discussion_messages, "discussion-message"),
    ],
)
async def test_resync_reads_exclude_flag_without_local_config_class(
    handler: Any, kind: str
) -> None:
    seen: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_discussions(
            self,
            statuses: list[str] | None = None,
            *,
            exclude_ai_discussions: bool = False,
        ) -> Any:
            seen["statuses"] = statuses
            seen["exclude_ai_discussions"] = exclude_ai_discussions
            yield []

        async def get_discussion_messages(
            self,
            statuses: list[str] | None = None,
            *,
            exclude_ai_discussions: bool = False,
        ) -> Any:
            seen["statuses"] = statuses
            seen["exclude_ai_discussions"] = exclude_ai_discussions
            yield []

    config = cast(
        ResourceConfig,
        SimpleNamespace(
            kind=kind,
            selector=SimpleNamespace(exclude_done_threads=False),
        ),
    )

    with patch("main.PlainClient", FakeClient):
        assert handler is not None
        async with resource_context(config):
            await collect_pages(handler(kind))

    assert seen["statuses"] is None


@pytest.mark.parametrize(
    ("handler", "kind"),
    [
        (on_resync_discussions, "discussion"),
        (on_resync_discussion_messages, "discussion-message"),
    ],
)
async def test_resync_passes_exclude_ai_discussions_when_flag_is_set(
    handler: Any, kind: str
) -> None:
    seen: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_discussions(
            self,
            statuses: list[str] | None = None,
            *,
            exclude_ai_discussions: bool = False,
        ) -> Any:
            seen["exclude_ai_discussions"] = exclude_ai_discussions
            yield [{"id": "disc_1"}]

        async def get_discussion_messages(
            self,
            statuses: list[str] | None = None,
            *,
            exclude_ai_discussions: bool = False,
        ) -> Any:
            seen["exclude_ai_discussions"] = exclude_ai_discussions
            yield [{"id": "dm_1", "threadId": "th_1"}]

    with patch("main.PlainClient", FakeClient):
        assert handler is not None
        async with resource_context(
            _resource(kind, False, exclude_ai_discussions=True)
        ):
            await collect_pages(handler(kind))

    assert seen["exclude_ai_discussions"] is True


async def test_get_discussions_batches_250_threads_into_3_calls() -> None:
    """With 250 threads and pageSize 100, makes 3 discussion batch calls."""
    client = make_client()
    call_count = 0

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        for i in range(3):
            count = 100 if i < 2 else 50
            yield [{"id": f"th_{j}"} for j in range(i * 100, i * 100 + count)]

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        nonlocal call_count
        call_count += 1
        yield []

    async with resource_context(_resource("discussion", False)):
        client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
        client.paginate_connection = paginate_connection  # type: ignore[method-assign]
        await collect_pages(client.get_discussions(None))

    assert call_count == 3


async def test_get_discussions_filters_by_thread_id() -> None:
    """Only discussions matching the requested threadIds are returned."""
    client = make_client()

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        yield [{"id": "th_1"}, {"id": "th_2"}]

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        yield [
            {"id": "disc_1", "threadId": "th_1"},
            {"id": "disc_2", "threadId": "th_2"},
            {"id": "disc_3", "threadId": "th_other"},
            {"id": "disc_4", "threadId": None},
        ]

    client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_discussions(None))

    assert len(batches[0]) == 2
    assert {d["id"] for d in batches[0]} == {"disc_1", "disc_2"}


async def test_get_discussions_does_not_call_with_empty_chunk() -> None:
    """When no thread IDs are found, no discussion call is made."""
    client = make_client()
    call_count = 0

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        yield []

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        nonlocal call_count
        call_count += 1
        yield []

    client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    await collect_pages(client.get_discussions(None))

    assert call_count == 0


async def test_get_discussion_messages_chunks_thread_ids() -> None:
    """Thread IDs are chunked by pageSize for discussion fetching."""
    client = make_client()
    seen_chunks: list[list[str]] = []

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        yield [{"id": "th_1"}, {"id": "th_2"}]

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        if operation_name == "ThreadDiscussionIds":
            assert variables is not None
            seen_chunks.append(variables["threadIds"])
            yield []
        else:
            yield []

    async with resource_context(_resource("discussion-message", False)):
        client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
        client.paginate_connection = paginate_connection  # type: ignore[method-assign]
        await collect_pages(client.get_discussion_messages(None))

    assert len(seen_chunks) == 1
    assert seen_chunks[0] == ["th_1", "th_2"]


async def test_discussions_query_includes_sortby() -> None:
    """ThreadDiscussions query includes sortBy for consistent ordering."""
    assert "sortBy:" in THREAD_DISCUSSIONS
    assert "CREATED_AT" in THREAD_DISCUSSIONS
    assert "ASC" in THREAD_DISCUSSIONS


async def test_get_discussions_parity_with_old_implementation() -> None:
    """New batched implementation yields same discussions as old per-thread approach."""
    client = make_client()

    # Fixture: threads and their discussions
    fixture_thread_ids: list[dict[str, Any]] = [{"id": "th_1"}, {"id": "th_2"}]
    fixture_discussions: list[dict[str, Any]] = [
        {"id": "disc_1", "threadId": "th_1", "title": "First"},
        {
            "id": "disc_ai",
            "threadId": "th_1",
            "channelDetails": {
                "__typename": "ThreadDiscussionAgentSessionChannelDetails"
            },
        },
        {"id": "disc_2", "threadId": "th_2", "title": "Second"},
        {"id": "disc_other", "threadId": "th_other", "title": "Other"},
    ]

    # Simulate old per-thread implementation with exclude_ai
    old_results: list[dict[str, Any]] = []
    for thread in fixture_thread_ids:
        thread_id = thread["id"]
        for disc in fixture_discussions:
            if disc.get("threadId") == thread_id:
                # Apply exclude_ai filter
                details = disc.get("channelDetails")
                if isinstance(details, dict):
                    typename = details.get("__typename", "")
                else:
                    typename = ""
                is_ai = "Agent" in typename or "Cursor" in typename
                if not is_ai:
                    old_results.append(disc)

    # Simulate new batched implementation
    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        yield fixture_thread_ids

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        yield fixture_discussions

    client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    new_batches = await collect_pages(
        client.get_discussions(None, exclude_ai_discussions=True)
    )
    new_results = [disc for batch in new_batches for disc in batch]

    # Verify parity
    assert len(old_results) == len(new_results)
    assert [d["id"] for d in old_results] == [d["id"] for d in new_results]
    # Verify threadId filtering worked (disc_other excluded)
    assert "disc_other" not in [d["id"] for d in new_results]
    # Verify exclude_ai worked (disc_ai excluded)
    assert "disc_ai" not in [d["id"] for d in new_results]


async def test_get_discussion_messages_parity_stamps_thread_id() -> None:
    """New implementation stamps threadId from discussion response."""
    client = make_client()

    # Old implementation: fetched discussions per thread, got threadId from loop
    old_thread_id = "th_1"
    old_messages = [{"id": "dm_1", "text": "Hello", "threadId": old_thread_id}]

    # New implementation: gets threadId from discussion response
    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        yield [{"id": "th_1"}]

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
        *,
        after: str | None = None,
    ) -> Any:
        if operation_name == "ThreadDiscussionIds":
            yield [{"id": "disc_1", "threadId": "th_1"}]
        else:
            yield [{"id": "dm_1", "text": "Hello"}]

    client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    new_batches = await collect_pages(client.get_discussion_messages(None))
    new_messages = [msg for batch in new_batches for msg in batch]

    # Verify parity: threadId stamping produces same result
    assert len(old_messages) == len(new_messages)
    assert new_messages[0]["threadId"] == old_thread_id
