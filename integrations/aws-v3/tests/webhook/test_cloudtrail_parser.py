from typing import Any

from aws.core.helpers.types import ObjectKind
from aws.webhook.cloudtrail_parser import (
    CloudTrailEventAction,
    is_supported_cloudtrail_event,
    parse_cloudtrail_event,
)


def _eventbridge_envelope(
    event_name: str,
    bucket_name: str | None = "my-bucket",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "eventName": event_name,
        "awsRegion": region,
        "recipientAccountId": account,
    }
    if bucket_name is not None:
        detail["requestParameters"] = {"bucketName": bucket_name}
    else:
        detail["requestParameters"] = {}

    return {
        "version": "0",
        "detail-type": "AWS API Call via CloudTrail",
        "source": "aws.s3",
        "account": account,
        "region": region,
        "detail": detail,
    }


def test_is_supported_cloudtrail_event_true_for_create() -> None:
    payload = _eventbridge_envelope("CreateBucket")
    assert is_supported_cloudtrail_event(payload) is True


def test_is_supported_cloudtrail_event_true_for_delete() -> None:
    payload = _eventbridge_envelope("DeleteBucket")
    assert is_supported_cloudtrail_event(payload) is True


def test_is_supported_cloudtrail_event_false_for_unsupported_event() -> None:
    payload = _eventbridge_envelope("PutBucketTagging")
    assert is_supported_cloudtrail_event(payload) is False


def test_is_supported_cloudtrail_event_false_for_malformed_payload() -> None:
    assert is_supported_cloudtrail_event({}) is False
    assert is_supported_cloudtrail_event({"detail": "not-a-dict"}) is False


def test_parse_create_bucket_event() -> None:
    payload = _eventbridge_envelope("CreateBucket", bucket_name="my-bucket")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.S3_BUCKET
    assert parsed.action == CloudTrailEventAction.UPSERT
    assert parsed.identifier == "my-bucket"
    assert parsed.account_id == "111122223333"
    assert parsed.region == "us-east-1"
    assert parsed.event_name == "CreateBucket"


def test_parse_delete_bucket_event() -> None:
    payload = _eventbridge_envelope("DeleteBucket", bucket_name="my-bucket")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.action == CloudTrailEventAction.DELETE


def test_parse_returns_none_for_unsupported_event() -> None:
    payload = _eventbridge_envelope("PutBucketTagging")
    assert parse_cloudtrail_event(payload) is None


def test_parse_returns_none_when_bucket_name_missing() -> None:
    payload = _eventbridge_envelope("CreateBucket", bucket_name=None)
    assert parse_cloudtrail_event(payload) is None


def test_parse_returns_none_when_account_missing() -> None:
    payload = _eventbridge_envelope("CreateBucket", account=None)
    assert parse_cloudtrail_event(payload) is None


def test_parse_falls_back_to_detail_recipient_account_id() -> None:
    payload = _eventbridge_envelope("CreateBucket")
    del payload["account"]

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.account_id == "111122223333"
