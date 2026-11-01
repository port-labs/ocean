from typing import Any

from plain.utils import ObjectKind, edges_to_nodes, get_nested, is_ai_discussion


def test_get_nested_returns_value_at_dotted_path() -> None:
    payload: dict[str, Any] = {"data": {"threads": {"totalCount": 2}}}

    assert get_nested(payload, "data.threads") == {"totalCount": 2}
    assert get_nested(payload, "data.threads.totalCount") == 2


def test_get_nested_returns_none_when_path_is_missing() -> None:
    payload: dict[str, Any] = {"data": {"companies": {"edges": []}}}

    assert get_nested(payload, "data.threads") is None
    assert get_nested(payload, "data.companies.pageInfo.hasNextPage") is None
    assert get_nested(None, "data.threads") is None


def test_edges_to_nodes_flattens_relay_edges() -> None:
    connection: dict[str, Any] = {
        "pageInfo": {"hasNextPage": False, "endCursor": None},
        "edges": [
            {"cursor": "c1", "node": {"id": "co_1", "name": "Acme"}},
            {"cursor": "c2", "node": {"id": "co_2", "name": "Beta"}},
        ],
    }

    assert edges_to_nodes(connection) == [
        {"id": "co_1", "name": "Acme"},
        {"id": "co_2", "name": "Beta"},
    ]


def test_edges_to_nodes_returns_empty_list_for_empty_connection() -> None:
    assert edges_to_nodes({"edges": [], "pageInfo": {"hasNextPage": False}}) == []
    assert edges_to_nodes(None) == []
    assert edges_to_nodes({"pageInfo": {"hasNextPage": False}}) == []


def test_object_kind_values_match_kind_strings() -> None:
    assert ObjectKind.COMPANY == "company"
    assert ObjectKind.TENANT == "tenant"
    assert ObjectKind.USER == "user"
    assert ObjectKind.MACHINE_USER == "machine-user"
    assert ObjectKind.CUSTOMER == "customer"
    assert ObjectKind.THREAD == "thread"
    assert ObjectKind.THREAD_MESSAGE == "thread-message"
    assert ObjectKind.DISCUSSION == "discussion"
    assert ObjectKind.DISCUSSION_MESSAGE == "discussion-message"
    assert [kind.value for kind in ObjectKind] == [
        "company",
        "tenant",
        "user",
        "machine-user",
        "customer",
        "thread",
        "thread-message",
        "discussion",
        "discussion-message",
    ]


def test_is_ai_discussion_detects_agent_channels() -> None:
    assert is_ai_discussion(
        {"channelDetails": {"__typename": "ThreadDiscussionAgentSessionChannelDetails"}}
    )
    assert is_ai_discussion(
        {
            "channelDetails": {
                "__typename": (
                    "ThreadDiscussionCursorWorkspaceBackgroundAgentChannelDetails"
                )
            }
        }
    )
    assert not is_ai_discussion(
        {"channelDetails": {"__typename": "ThreadDiscussionSlackChannelDetails"}}
    )
    assert not is_ai_discussion(
        {"channelDetails": {"__typename": "ThreadDiscussionEmailChannelDetails"}}
    )
    assert not is_ai_discussion({"channelDetails": None})
    assert not is_ai_discussion(None)
