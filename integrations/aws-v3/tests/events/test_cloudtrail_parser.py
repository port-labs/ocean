from typing import Any

from aws.events.cloudtrail_parser import (
    S3BucketLiveEventAction,
    is_supported_s3_bucket_event,
    parse_s3_bucket_event,
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


def test_is_supported_s3_bucket_event_true_for_create() -> None:
    payload = _eventbridge_envelope("CreateBucket")
    assert is_supported_s3_bucket_event(payload) is True


def test_is_supported_s3_bucket_event_true_for_delete() -> None:
    payload = _eventbridge_envelope("DeleteBucket")
    assert is_supported_s3_bucket_event(payload) is True


def test_is_supported_s3_bucket_event_false_for_unsupported_event() -> None:
    payload = _eventbridge_envelope("PutBucketTagging")
    assert is_supported_s3_bucket_event(payload) is False


def test_is_supported_s3_bucket_event_false_for_malformed_payload() -> None:
    assert is_supported_s3_bucket_event({}) is False
    assert is_supported_s3_bucket_event({"detail": "not-a-dict"}) is False


def test_parse_create_bucket_event() -> None:
    payload = _eventbridge_envelope("CreateBucket", bucket_name="my-bucket")

    parsed = parse_s3_bucket_event(payload)

    assert parsed is not None
    assert parsed.action == S3BucketLiveEventAction.UPSERT
    assert parsed.bucket_name == "my-bucket"
    assert parsed.account_id == "111122223333"
    assert parsed.region == "us-east-1"
    assert parsed.event_name == "CreateBucket"


def test_parse_delete_bucket_event() -> None:
    payload = _eventbridge_envelope("DeleteBucket", bucket_name="my-bucket")

    parsed = parse_s3_bucket_event(payload)

    assert parsed is not None
    assert parsed.action == S3BucketLiveEventAction.DELETE


def test_parse_returns_none_for_unsupported_event() -> None:
    payload = _eventbridge_envelope("PutBucketTagging")
    assert parse_s3_bucket_event(payload) is None


def test_parse_returns_none_when_bucket_name_missing() -> None:
    payload = _eventbridge_envelope("CreateBucket", bucket_name=None)
    assert parse_s3_bucket_event(payload) is None


def test_parse_returns_none_when_account_missing() -> None:
    payload = _eventbridge_envelope("CreateBucket", account=None)
    assert parse_s3_bucket_event(payload) is None


def test_parse_falls_back_to_detail_recipient_account_id() -> None:
    payload = _eventbridge_envelope("CreateBucket")
    del payload["account"]

    parsed = parse_s3_bucket_event(payload)

    assert parsed is not None
    assert parsed.account_id == "111122223333"
