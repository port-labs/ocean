"""Tests for batched per-thread fetches using MockTransport seam."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
from port_ocean.context.resource import resource_context

from plain.client import PlainClient
from tests.kind_helpers import collect_pages


def _mock_client(handler: Any) -> PlainClient:
    """Create a client with MockTransport that calls handler(request) for each request."""
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {
        "api_token": "plainApiKey_test",
        "api_url": "https://core-api.uk.plain.com/graphql/v1",
    }
    mock_ocean.config.integration.identifier = "plain"
    mock_ocean.config.client_timeout = 30
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("plain.client.ocean", mock_ocean):
        return PlainClient(http_client=http_client)


def _graphql_response(data: dict[str, Any]) -> httpx.Response:
    """Create a JSON GraphQL response."""
    return httpx.Response(200, json={"data": data})


def _page(
    nodes: list[dict[str, Any]], has_next: bool, cursor: str | None
) -> dict[str, Any]:
    """Build a Relay connection page."""
    return {
        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
        "edges": [{"node": node} for node in nodes],
    }


def _thread_with_timeline(
    thread_id: str,
    entries: list[dict[str, Any]],
    has_next: bool,
    cursor: str | None,
) -> dict[str, Any]:
    """Build a thread node with nested timelineEntries."""
    return {
        "id": thread_id,
        "timelineEntries": _page(entries, has_next, cursor),
    }


def _resource(page_size: int = 100) -> Any:
    """Minimal resource config for context."""
    return SimpleNamespace(
        kind="thread-message",
        selector=SimpleNamespace(page_size=page_size),
    )


async def test_thread_messages_uses_list_thread_timelines_with_timeline_first() -> None:
    """get_thread_messages calls LIST_THREAD_TIMELINES with timelineFirst variable."""
    seen_requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        import json

        payload = json.loads(body)
        seen_requests.append(payload)
        # Return empty threads
        return _graphql_response({"threads": _page([], False, None)})

    client = _mock_client(handler)
    async with resource_context(_resource()):
        await collect_pages(client.get_thread_messages(None))

    assert len(seen_requests) == 1
    assert "ListThreadTimelines" in seen_requests[0]["query"]
    assert seen_requests[0]["variables"]["timelineFirst"] == 50


async def test_thread_messages_filters_by_llm_text() -> None:
    """Only timeline entries with non-empty llmText are yielded."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _graphql_response(
            {
                "threads": _page(
                    [
                        _thread_with_timeline(
                            "th_1",
                            [
                                {"id": "tl_1", "llmText": "Hello", "threadId": "th_1"},
                                {"id": "tl_2", "llmText": "", "threadId": "th_1"},
                                {"id": "tl_3", "llmText": "  ", "threadId": "th_1"},
                            ],
                            False,
                            None,
                        )
                    ],
                    False,
                    None,
                )
            }
        )

    client = _mock_client(handler)
    async with resource_context(_resource()):
        batches = await collect_pages(client.get_thread_messages(None))

    assert len(batches) == 1
    assert [e["id"] for e in batches[0]] == ["tl_1"]


async def test_thread_messages_nested_cursor_follow_up_carries_after() -> None:
    """When nested hasNextPage is true, follow-up THREAD_TIMELINE carries after=endCursor."""
    seen_requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.read().decode())
        seen_requests.append(body)
        if body["operationName"] == "ListThreadTimelines":
            return _graphql_response(
                {
                    "threads": _page(
                        [
                            _thread_with_timeline(
                                "th_1",
                                [
                                    {
                                        "id": "tl_1",
                                        "llmText": "First",
                                        "threadId": "th_1",
                                    }
                                ],
                                True,
                                "cursor-nested-1",
                            )
                        ],
                        False,
                        None,
                    )
                }
            )
        else:  # ThreadTimeline
            return _graphql_response(
                {
                    "thread": {
                        "timelineEntries": _page(
                            [{"id": "tl_2", "llmText": "Second", "threadId": "th_1"}],
                            False,
                            None,
                        )
                    }
                }
            )

    client = _mock_client(handler)
    async with resource_context(_resource()):
        batches = await collect_pages(client.get_thread_messages(None))

    assert len(seen_requests) == 2
    assert seen_requests[0]["operationName"] == "ListThreadTimelines"
    assert seen_requests[1]["operationName"] == "ThreadTimeline"
    assert seen_requests[1]["variables"]["after"] == "cursor-nested-1"
    assert len(batches) == 2
    assert batches[0][0]["id"] == "tl_1"
    assert batches[1][0]["id"] == "tl_2"


async def test_thread_messages_two_page_follow_up_no_gaps_or_duplicates() -> None:
    """Two-page follow-up yields entries in order with no gaps or duplicates."""
    seen_requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.read().decode())
        seen_requests.append(body)
        if body["operationName"] == "ListThreadTimelines":
            return _graphql_response(
                {
                    "threads": _page(
                        [
                            _thread_with_timeline(
                                "th_1",
                                [
                                    {
                                        "id": "tl_1",
                                        "llmText": "First",
                                        "threadId": "th_1",
                                    }
                                ],
                                True,
                                "cursor-nested-1",
                            )
                        ],
                        False,
                        None,
                    )
                }
            )
        else:  # ThreadTimeline
            after = body["variables"].get("after")
            if after == "cursor-nested-1":
                return _graphql_response(
                    {
                        "thread": {
                            "timelineEntries": _page(
                                [
                                    {
                                        "id": "tl_2",
                                        "llmText": "Second",
                                        "threadId": "th_1",
                                    }
                                ],
                                True,
                                "cursor-nested-2",
                            )
                        }
                    }
                )
            else:  # after == "cursor-nested-2"
                return _graphql_response(
                    {
                        "thread": {
                            "timelineEntries": _page(
                                [
                                    {
                                        "id": "tl_3",
                                        "llmText": "Third",
                                        "threadId": "th_1",
                                    }
                                ],
                                False,
                                None,
                            )
                        }
                    }
                )

    client = _mock_client(handler)
    async with resource_context(_resource()):
        batches = await collect_pages(client.get_thread_messages(None))

    # Verify order and no duplicates
    all_ids = [e["id"] for batch in batches for e in batch]
    assert all_ids == ["tl_1", "tl_2", "tl_3"]


async def test_discussions_batches_thread_ids() -> None:
    """get_discussions passes threadIds array to THREAD_DISCUSSIONS."""
    seen_requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.read().decode())
        seen_requests.append(body)
        if body["operationName"] == "ListThreadIds":
            return _graphql_response(
                {"threads": _page([{"id": "th_1"}, {"id": "th_2"}], False, None)}
            )
        else:  # ThreadDiscussions
            return _graphql_response(
                {
                    "discussions": _page(
                        [
                            {"id": "disc_1", "threadId": "th_1"},
                            {"id": "disc_2", "threadId": "th_2"},
                        ],
                        False,
                        None,
                    )
                }
            )

    client = _mock_client(handler)
    async with resource_context(_resource()):
        batches = await collect_pages(client.get_discussions(None))

    assert len(seen_requests) == 2
    assert seen_requests[1]["operationName"] == "ThreadDiscussions"
    assert seen_requests[1]["variables"]["threadIds"] == ["th_1", "th_2"]
    assert len(batches[0]) == 2


async def test_discussion_messages_thread_id_in_query_and_stamped() -> None:
    """THREAD_DISCUSSION_IDS selects threadId and each message gets its discussion's threadId."""
    seen_requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.read().decode())
        seen_requests.append(body)
        op = body["operationName"]
        if op == "ListThreadIds":
            return _graphql_response(
                {"threads": _page([{"id": "th_1"}, {"id": "th_2"}], False, None)}
            )
        elif op == "ThreadDiscussionIds":
            return _graphql_response(
                {
                    "discussions": _page(
                        [
                            {"id": "disc_1", "threadId": "th_1"},
                            {"id": "disc_2", "threadId": "th_2"},
                        ],
                        False,
                        None,
                    )
                }
            )
        else:  # DiscussionMessages
            disc_id = body["variables"]["discussionId"]
            thread_id = "th_1" if disc_id == "disc_1" else "th_2"
            return _graphql_response(
                {
                    "discussion": {
                        "threadId": thread_id,
                        "messages": _page(
                            [
                                {
                                    "id": f"dm_{disc_id}",
                                    "text": "Message",
                                    "threadDiscussionId": disc_id,
                                }
                            ],
                            False,
                            None,
                        ),
                    }
                }
            )

    client = _mock_client(handler)
    async with resource_context(_resource()):
        batches = await collect_pages(client.get_discussion_messages(None))

    # Verify threadId is in THREAD_DISCUSSION_IDS query
    disc_ids_request = seen_requests[1]
    assert "threadId" in disc_ids_request["query"]

    # Verify each message has correct threadId
    all_messages = [msg for batch in batches for msg in batch]
    assert len(all_messages) == 2
    assert all_messages[0]["threadId"] == "th_1"
    assert all_messages[1]["threadId"] == "th_2"


async def test_thread_list_variables_empty_list_sends_no_filter() -> None:
    """When statuses is [], _thread_list_variables returns {} so no filter is sent."""
    seen_requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.read().decode())
        seen_requests.append(body)
        return _graphql_response({"threads": _page([], False, None)})

    client = _mock_client(handler)
    async with resource_context(_resource()):
        await collect_pages(client.get_thread_messages([]))

    # Empty list should send no filters key
    assert "filters" not in seen_requests[0]["variables"]
