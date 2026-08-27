"""CloudTrail-via-EventBridge parser for aws-v3 live events.

Maps CloudTrail ``eventName`` values to a normalized event that the single
``CloudTrailWebhookProcessor`` can route through ``kind_to_export_metadata``.
"""

from dataclasses import dataclass

from loguru import logger

from aws.core.helpers.metadata.cloudtrail_event_mappings import (
    EVENT_NAME_MAPPINGS,
    cloudtrail_mapping_key,
)
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    EventBridgeCloudTrailPayload,
    EventNameMapping,
)

__all__ = [
    "CloudTrailDetail",
    "CloudTrailEventAction",
    "EventBridgeCloudTrailPayload",
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


def _get_detail(payload: EventBridgeCloudTrailPayload) -> CloudTrailDetail:
    detail = payload.get("detail")
    return detail if isinstance(detail, dict) else {}


def get_event_name(payload: EventBridgeCloudTrailPayload) -> str | None:
    """Extract the CloudTrail eventName from an EventBridge envelope."""
    return _get_detail(payload).get("eventName")


def _resolve_event_mapping(detail: CloudTrailDetail) -> EventNameMapping | None:
    return EVENT_NAME_MAPPINGS.get(
        cloudtrail_mapping_key(detail.get("eventName"), detail.get("eventSource"))
    )


def is_supported_cloudtrail_event(payload: EventBridgeCloudTrailPayload) -> bool:
    detail = _get_detail(payload)
    if detail.get("errorCode"):
        logger.warning(
            f"CloudTrail event has error code {detail['errorCode']}; "
            f"skipping live event (eventName={detail.get('eventName')})"
        )
        return False
    return _resolve_event_mapping(detail) is not None


def parse_cloudtrail_event(
    payload: EventBridgeCloudTrailPayload,
) -> NormalizedEvent | None:
    """Parse an EventBridge/CloudTrail payload into a normalized live event.

    Returns ``None`` when required fields are missing, the API call failed
    (``errorCode`` present), or the event is not mapped to a supported kind.
    """
    detail = _get_detail(payload)
    if detail.get("errorCode"):
        return None

    event_name = detail.get("eventName")
    if not event_name:
        return None

    mapping = _resolve_event_mapping(detail)
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
