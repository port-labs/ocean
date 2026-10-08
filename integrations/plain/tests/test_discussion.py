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
    assert "threadIds: [$threadId]" in THREAD_DISCUSSIONS
    assert "slackMessageLink" in THREAD_DISCUSSIONS
    assert "emailRecipients" in THREAD_DISCUSSIONS
    assert "userId" in THREAD_DISCUSSIONS
    assert "channelDetails" in THREAD_DISCUSSION_IDS
    assert "__typename" in THREAD_DISCUSSION_IDS
    assert "discussion(discussionId: $discussionId)" in DISCUSSION_MESSAGES
    assert "slackMessageLink" in DISCUSSION_MESSAGES


def test_discussion_kinds_are_registered_in_spec() -> None:
    kinds = exporter_kinds()
    assert "kind: discussion\n" in kinds
    assert "kind: discussion-message" in kinds


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


async def test_get_discussions_pages_each_thread() -> None:
    client = make_client()
    seen: dict[str, Any] = {}

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        seen["statuses"] = statuses
        yield [{"id": "th_1"}, {"id": ""}]

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
        yield [{"id": "disc_1", "threadId": "th_1", "title": "Check the refund"}]

    client.get_thread_ids = get_thread_ids  # type: ignore[method-assign]
    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_discussions(["TODO", "SNOOZED"]))

    assert seen["statuses"] == ["TODO", "SNOOZED"]
    assert seen["query"] is THREAD_DISCUSSIONS
    assert seen["operation_name"] == "ThreadDiscussions"
    assert seen["variables"] == {"threadId": "th_1"}
    assert seen["connection_path"] == "discussions"
    assert batches[0][0]["id"] == "disc_1"


async def test_get_discussions_skips_ai_channels_when_requested() -> None:
    client = make_client()

    async def get_thread_ids(statuses: list[str] | None = None) -> Any:
        yield [{"id": "th_1"}]

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
    ) -> Any:
        yield [
            {
                "id": "disc_slack",
                "channelDetails": {"__typename": "ThreadDiscussionSlackChannelDetails"},
            },
            {
                "id": "disc_agent",
                "channelDetails": {
                    "__typename": "ThreadDiscussionAgentSessionChannelDetails"
                },
            },
            {
                "id": "disc_cursor",
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
            yield [{"id": "disc_1"}]
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
    ) -> Any:
        if operation_name == "ThreadDiscussionIds":
            yield [
                {
                    "id": "disc_human",
                    "channelDetails": {
                        "__typename": "ThreadDiscussionSlackChannelDetails"
                    },
                },
                {
                    "id": "disc_agent",
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
    ) -> Any:
        if operation_name == "ThreadDiscussionIds":
            yield [{"id": "disc_missing"}]
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
