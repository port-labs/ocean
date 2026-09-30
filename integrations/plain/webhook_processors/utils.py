from __future__ import annotations

from typing import Any

from port_ocean.core.handlers.webhook.webhook_event import EventPayload


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
    return entity_id(body.get("discussion"))


def discussion_thread_id(body: dict[str, Any]) -> str | None:
    discussion = body.get("discussion")
    if isinstance(discussion, dict):
        return entity_id(discussion.get("threadId"))
    return None


def discussion_message_id(body: dict[str, Any]) -> str | None:
    return entity_id(body.get("message"))


def tenant_id_from_payload(body: dict[str, Any]) -> str | None:
    return entity_id(body.get("tenant"))


def assignee_user_id(body: dict[str, Any]) -> str | None:
    thread = body.get("thread")
    if not isinstance(thread, dict):
        return None
    assignee = thread.get("assignee")
    if not isinstance(assignee, dict):
        return None
    # Webhook user objects include email; machine users do not.
    if "email" not in assignee:
        return None
    return entity_id(assignee)


def timeline_entry_refs(body: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return ``(customer_id, timeline_entry_id)`` for message-like events."""
    timeline_entry = body.get("timelineEntry")
    if isinstance(timeline_entry, dict):
        return entity_id(timeline_entry.get("customerId")), entity_id(timeline_entry)

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
