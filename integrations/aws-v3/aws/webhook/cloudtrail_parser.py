"""CloudTrail-via-EventBridge parser for aws-v3 live events.

Maps CloudTrail ``eventName`` values to a normalized event that the single
``CloudTrailWebhookProcessor`` can route through ``kind_to_export_metadata``.
"""

from dataclasses import dataclass
from typing import Any

from aws.webhook.event_name_mappings import (
    EVENT_NAME_MAPPINGS,
    CloudTrailEventAction,
)

__all__ = [
    "CloudTrailEventAction",
    "EVENT_NAME_MAPPINGS",
    "NormalizedEvent",
    "get_event_name",
    "is_supported_cloudtrail_event",
    "parse_cloudtrail_event",
]


@dataclass(frozen=True)
class NormalizedEvent:
    kind: str
    identifier: str
    account_id: str
    region: str
    action: CloudTrailEventAction
    event_name: str


def _get_detail(payload: dict[str, Any]) -> dict[str, Any]:
    detail = payload.get("detail")
    return detail if isinstance(detail, dict) else {}


def get_event_name(payload: dict[str, Any]) -> str | None:
    """Extract the CloudTrail eventName from an EventBridge envelope."""
    event_name = _get_detail(payload).get("eventName")
    return event_name if isinstance(event_name, str) else None


def _has_error_code(detail: dict[str, Any]) -> bool:
    """Return True when the CloudTrail event records a failed API call."""
    error_code = detail.get("errorCode")
    return isinstance(error_code, str) and bool(error_code)


def is_supported_cloudtrail_event(payload: dict[str, Any]) -> bool:
    detail = _get_detail(payload)
    if _has_error_code(detail):
        return False
    event_name = get_event_name(payload)
    return event_name in EVENT_NAME_MAPPINGS if event_name is not None else False


def parse_cloudtrail_event(payload: dict[str, Any]) -> NormalizedEvent | None:
    """Parse an EventBridge/CloudTrail payload into a normalized live event.

    Returns ``None`` when required fields are missing, the API call failed
    (``errorCode`` present), or the event is not mapped to a supported kind.
    """
    detail = _get_detail(payload)
    if _has_error_code(detail):
        return None

    event_name = detail.get("eventName")
    if not isinstance(event_name, str):
        return None

    mapping = EVENT_NAME_MAPPINGS.get(event_name)
    if mapping is None:
        return None

    identifier = mapping.extract_identifier(detail)
    account_id = payload.get("account") or detail.get("recipientAccountId")
    region = payload.get("region") or detail.get("awsRegion")

    if not identifier or not account_id or not region:
        return None

    return NormalizedEvent(
        kind=mapping.kind,
        identifier=identifier,
        account_id=str(account_id),
        region=str(region),
        action=mapping.action,
        event_name=event_name,
    )
