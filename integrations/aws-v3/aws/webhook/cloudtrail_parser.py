"""CloudTrail-via-EventBridge parser for aws-v3 live events.

Maps CloudTrail ``eventName`` values to a normalized event that the single
``CloudTrailWebhookProcessor`` can route through the exporter registry.

Expected payload shape (as delivered by an EventBridge API Destination):

{
    "version": "0",
    "detail-type": "AWS API Call via CloudTrail",
    "source": "aws.s3",
    "account": "111122223333",
    "region": "us-east-1",
    "detail": {
        "eventName": "CreateBucket",
        "awsRegion": "us-east-1",
        "recipientAccountId": "111122223333",
        "requestParameters": {"bucketName": "my-bucket"},
        ...
    }
}
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aws.core.helpers.types import ObjectKind


class CloudTrailEventAction(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


@dataclass(frozen=True)
class NormalizedEvent:
    kind: str
    identifier: str
    account_id: str
    region: str
    action: CloudTrailEventAction
    event_name: str


@dataclass(frozen=True)
class _EventNameMapping:
    kind: str
    action: CloudTrailEventAction
    extract_identifier: Callable[[dict[str, Any]], str | None]


def _extract_s3_bucket_name(detail: dict[str, Any]) -> str | None:
    bucket_name = detail.get("requestParameters", {}).get("bucketName")
    return bucket_name if isinstance(bucket_name, str) and bucket_name else None


EVENT_NAME_MAPPINGS: dict[str, _EventNameMapping] = {
    "CreateBucket": _EventNameMapping(
        ObjectKind.S3_BUCKET, CloudTrailEventAction.UPSERT, _extract_s3_bucket_name
    ),
    "DeleteBucket": _EventNameMapping(
        ObjectKind.S3_BUCKET, CloudTrailEventAction.DELETE, _extract_s3_bucket_name
    ),
}


def _get_detail(payload: dict[str, Any]) -> dict[str, Any]:
    detail = payload.get("detail")
    return detail if isinstance(detail, dict) else {}


def get_event_name(payload: dict[str, Any]) -> str | None:
    """Extract the CloudTrail eventName from an EventBridge envelope."""
    event_name = _get_detail(payload).get("eventName")
    return event_name if isinstance(event_name, str) else None


def is_supported_cloudtrail_event(payload: dict[str, Any]) -> bool:
    event_name = get_event_name(payload)
    return event_name in EVENT_NAME_MAPPINGS if event_name is not None else False


def parse_cloudtrail_event(payload: dict[str, Any]) -> NormalizedEvent | None:
    """Parse an EventBridge/CloudTrail payload into a normalized live event.

    Returns ``None`` when required fields are missing or the event is not
    mapped to a supported kind.
    """
    detail = _get_detail(payload)
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
