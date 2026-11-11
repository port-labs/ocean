from enum import StrEnum
from typing import Any


class ObjectKind(StrEnum):
    COMPANY = "company"
    TENANT = "tenant"
    USER = "user"
    MACHINE_USER = "machine-user"
    CUSTOMER = "customer"
    THREAD = "thread"
    THREAD_MESSAGE = "thread-message"
    DISCUSSION = "discussion"
    DISCUSSION_MESSAGE = "discussion-message"


AI_DISCUSSION_CHANNEL_TYPES = frozenset(
    {
        "ThreadDiscussionCursorWorkspaceBackgroundAgentChannelDetails",
        "ThreadDiscussionAgentSessionChannelDetails",
    }
)


def is_ai_discussion(discussion: dict[str, Any] | None) -> bool:
    """True when the discussion is an AI/agent session rather than Slack/email."""
    if not isinstance(discussion, dict):
        return False
    details = discussion.get("channelDetails")
    if not isinstance(details, dict):
        return False
    return details.get("__typename") in AI_DISCUSSION_CHANNEL_TYPES


def get_nested(data: dict[str, Any] | None, path: str) -> Any:
    """Return the value at a dotted path, or None if any segment is missing."""
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def edges_to_nodes(connection: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Flatten a Relay connection's ``edges`` into a list of ``node`` dicts."""
    if not isinstance(connection, dict):
        return []

    edges = connection.get("edges")
    if not isinstance(edges, list):
        return []

    nodes: list[dict[str, Any]] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        node = edge.get("node")
        if isinstance(node, dict):
            nodes.append(node)
    return nodes
