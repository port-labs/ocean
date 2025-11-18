from typing import Iterator, Tuple, Dict, Any

from port_ocean.core.handlers.webhook.webhook_event import EventPayload


def iter_event_targets(payload: EventPayload) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Yield (event_type, target) for each target in each event."""
    for event_object in payload["data"]["events"]:
        event_type = event_object["eventType"]
        for target in event_object["target"]:
            yield event_type, target


def any_target_of_type(payload: EventPayload, target_type: str) -> bool:
    """Return True if any target with the given type and an id exists in payload."""
    return any(
        target["type"] == target_type and target["id"]
        for _event_type, target in iter_event_targets(payload)
    )
