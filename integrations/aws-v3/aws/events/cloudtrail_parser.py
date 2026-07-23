"""Minimal CloudTrail-via-EventBridge parser for the S3 bucket live events POC.

This intentionally supports only the two events required to keep an
``AWS::S3::Bucket`` entity in sync: bucket creation and bucket deletion.
Any other CloudTrail event for S3 is ignored.

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

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class S3BucketLiveEventAction(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


CREATE_BUCKET_EVENTS = frozenset({"CreateBucket"})
DELETE_BUCKET_EVENTS = frozenset({"DeleteBucket"})
SUPPORTED_S3_BUCKET_EVENTS = CREATE_BUCKET_EVENTS | DELETE_BUCKET_EVENTS


@dataclass(frozen=True)
class S3BucketLiveEvent:
    action: S3BucketLiveEventAction
    bucket_name: str
    account_id: str
    region: str
    event_name: str


def _get_detail(payload: dict[str, Any]) -> dict[str, Any]:
    detail = payload.get("detail")
    return detail if isinstance(detail, dict) else {}


def get_event_name(payload: dict[str, Any]) -> str | None:
    """Extract the CloudTrail eventName from an EventBridge envelope."""
    return _get_detail(payload).get("eventName")


def is_supported_s3_bucket_event(payload: dict[str, Any]) -> bool:
    return get_event_name(payload) in SUPPORTED_S3_BUCKET_EVENTS


def parse_s3_bucket_event(payload: dict[str, Any]) -> S3BucketLiveEvent | None:
    """Parse an EventBridge/CloudTrail payload into a normalized S3 bucket event.

    Returns ``None`` when required fields are missing, e.g. malformed payload
    or an event that isn't one of the supported bucket events.
    """
    detail = _get_detail(payload)
    event_name = detail.get("eventName")
    if event_name not in SUPPORTED_S3_BUCKET_EVENTS:
        return None

    bucket_name = detail.get("requestParameters", {}).get("bucketName")
    account_id = payload.get("account") or detail.get("recipientAccountId")
    region = payload.get("region") or detail.get("awsRegion")

    if not bucket_name or not account_id or not region:
        return None

    action = (
        S3BucketLiveEventAction.DELETE
        if event_name in DELETE_BUCKET_EVENTS
        else S3BucketLiveEventAction.UPSERT
    )

    return S3BucketLiveEvent(
        action=action,
        bucket_name=bucket_name,
        account_id=account_id,
        region=region,
        event_name=event_name,
    )
