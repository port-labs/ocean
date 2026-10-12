from __future__ import annotations

from typing import Any

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import EventPayload

from plain.client import PlainClient


def event_type(payload: EventPayload) -> str:
    raw = payload.get("type")
    if isinstance(raw, str) and raw:
        return raw
    nested = payload.get("payload")
    if isinstance(nested, dict):
        nested_type = nested.get("eventType")
        if isinstance(nested_type, str):
            return nested_type
    return ""


def event_payload(payload: EventPayload) -> dict[str, Any]:
    nested = payload.get("payload")
    if isinstance(nested, dict):
        return nested
    return {}


def entity_id(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        raw = value.get("id")
        if isinstance(raw, str) and raw:
            return raw
    return None


def thread_id_from_payload(body: dict[str, Any]) -> str | None:
    return entity_id(body.get("thread"))


def customer_id_from_payload(
    body: dict[str, Any], *, deleted: bool = False
) -> str | None:
    key = "previousCustomer" if deleted else "customer"
    return entity_id(body.get(key)) or entity_id(body.get("customer"))


def discussion_id_from_payload(body: dict[str, Any]) -> str | None:
    # Schema events nest ``discussion.id``; some approval payloads use
    # a top-level ``discussionId`` string instead.
    return entity_id(body.get("discussion")) or entity_id(body.get("discussionId"))


def discussion_thread_id(body: dict[str, Any]) -> str | None:
    discussion = body.get("discussion")
    if isinstance(discussion, dict):
        nested = entity_id(discussion.get("threadId"))
        if nested:
            return nested
    return entity_id(body.get("threadId"))


def discussion_message_id(body: dict[str, Any]) -> str | None:
    return entity_id(body.get("message")) or entity_id(body.get("messageId"))


def tenant_id_from_payload(body: dict[str, Any]) -> str | None:
    return entity_id(body.get("tenant"))


def _thread_assignee(body: dict[str, Any]) -> dict[str, Any] | None:
    thread = body.get("thread")
    if not isinstance(thread, dict):
        return None
    assignee = thread.get("assignee")
    if not isinstance(assignee, dict):
        return None
    return assignee


def _assignee_kind(assignee: dict[str, Any]) -> str | None:
    """Return ``User``, ``MachineUser``, ``System``, or ``None`` if unknown."""
    for key in ("__typename", "type"):
        raw = assignee.get(key)
        if not isinstance(raw, str) or not raw:
            continue
        if raw in {"User", "MachineUser", "System"}:
            return raw
        # GraphQL MachineUser.type enum sometimes appears on assignee objects.
        if raw in {"API_USER", "AI_AGENT"}:
            return "MachineUser"
        if raw == "UNKNOWN":
            return None
    return None


def assignee_user_id(body: dict[str, Any]) -> str | None:
    assignee = _thread_assignee(body)
    if assignee is None:
        return None
    kind = _assignee_kind(assignee)
    if kind == "User":
        return entity_id(assignee)
    if kind in {"MachineUser", "System"}:
        return None
    # Webhook User includes email; MachineUser and System do not.
    if "email" not in assignee:
        return None
    return entity_id(assignee)


def assignee_machine_user_id(body: dict[str, Any]) -> str | None:
    assignee = _thread_assignee(body)
    if assignee is None:
        return None
    kind = _assignee_kind(assignee)
    if kind == "MachineUser":
        return entity_id(assignee)
    if kind in {"User", "System"}:
        return None
    # Plain webhook ThreadAssignee: user (has email), machineUser (profile
    # fields, no email), or System ({id} only). Prefer type/__typename above.
    if "email" in assignee:
        return None
    if "fullName" in assignee or "publicName" in assignee:
        return entity_id(assignee)
    assignee_id = entity_id(assignee)
    # Plain machine-user ids are prefixed ``mu_``; System assignees are id-only
    # without that prefix in practice.
    if assignee_id and assignee_id.startswith("mu_"):
        return assignee_id
    return None


def timeline_entry_refs(body: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return ``(customer_id, timeline_entry_id)`` for message-like events.

    ``timeline.timeline_entry_changed`` sets ``timelineEntry`` to null on
    ``REMOVED`` and puts the removed entry in ``previousTimelineEntry``.
    """
    timeline_entry = body.get("timelineEntry")
    if isinstance(timeline_entry, dict):
        return entity_id(timeline_entry.get("customerId")), entity_id(timeline_entry)

    previous = body.get("previousTimelineEntry")
    if isinstance(previous, dict):
        return entity_id(previous.get("customerId")), entity_id(previous)

    thread = body.get("thread")
    customer_id = None
    if isinstance(thread, dict):
        customer = thread.get("customer")
        customer_id = entity_id(customer)

    for key in (
        "email",
        "chat",
        "slackMessage",
        "discordMessage",
        "msTeamsMessage",
        "note",
    ):
        message = body.get(key)
        if isinstance(message, dict):
            entry_id = entity_id(message.get("timelineEntryId")) or entity_id(message)
            if entry_id:
                return customer_id, entry_id
    return customer_id, None


def is_timeline_removed(body: dict[str, Any]) -> bool:
    return body.get("changeType") == "REMOVED"


async def is_excluded_done_thread(
    client: PlainClient,
    resource_config: ResourceConfig,
    thread_id: str | None,
) -> bool:
    """True when excludeDoneThreads is set and the parent thread status is DONE."""
    if not thread_id:
        return False
    if not bool(getattr(resource_config.selector, "exclude_done_threads", False)):
        return False
    thread = await client.get_thread(thread_id)
    return thread.get("status") == "DONE"
