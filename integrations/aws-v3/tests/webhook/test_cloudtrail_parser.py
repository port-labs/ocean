from typing import cast

from aws.core.helpers.types import ObjectKind
from aws.webhook.cloudtrail_parser import (
    CloudTrailDetail,
    CloudTrailEventAction,
    EventBridgeCloudTrailPayload,
    is_supported_cloudtrail_event,
    parse_cloudtrail_event,
)


def _eventbridge_envelope(
    event_name: str,
    bucket_name: str | None = "my-bucket",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {"eventName": event_name}
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account
    if bucket_name is not None:
        detail["requestParameters"] = {"bucketName": bucket_name}
    else:
        detail["requestParameters"] = {}

    payload: EventBridgeCloudTrailPayload = {
        "detail": detail,
    }
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.s3",
        },
    )


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
    assert (
        is_supported_cloudtrail_event(
            cast(EventBridgeCloudTrailPayload, {"detail": "not-a-dict"})
        )
        is False
    )


def test_is_supported_cloudtrail_event_false_when_error_code_present() -> None:
    payload = _eventbridge_envelope("DeleteBucket")
    payload["detail"]["errorCode"] = "AccessDenied"
    assert is_supported_cloudtrail_event(payload) is False


def test_parse_returns_none_when_error_code_present() -> None:
    payload = _eventbridge_envelope("DeleteBucket")
    payload["detail"]["errorCode"] = "BucketNotEmpty"
    payload["detail"]["errorMessage"] = "The bucket you tried to delete is not empty"
    assert parse_cloudtrail_event(payload) is None


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


def _lambda_eventbridge_envelope(
    event_name: str,
    function_name: str | None = "my-function",
    account: str | None = "111122223333",
    region: str | None = "us-east-1",
) -> EventBridgeCloudTrailPayload:
    detail: CloudTrailDetail = {"eventName": event_name}
    if region is not None:
        detail["awsRegion"] = region
    if account is not None:
        detail["recipientAccountId"] = account
    if function_name is not None:
        detail["requestParameters"] = {"functionName": function_name}
    else:
        detail["requestParameters"] = {}

    payload: EventBridgeCloudTrailPayload = {
        "detail": detail,
    }
    if account is not None:
        payload["account"] = account
    if region is not None:
        payload["region"] = region
    return cast(
        EventBridgeCloudTrailPayload,
        {
            **payload,
            "version": "0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.lambda",
        },
    )


def test_is_supported_cloudtrail_event_true_for_create_function() -> None:
    payload = _lambda_eventbridge_envelope("CreateFunction20150331")
    assert is_supported_cloudtrail_event(payload) is True


def test_is_supported_cloudtrail_event_true_for_delete_function() -> None:
    payload = _lambda_eventbridge_envelope("DeleteFunction20150331")
    assert is_supported_cloudtrail_event(payload) is True


def test_is_supported_cloudtrail_event_false_for_unversioned_lambda_names() -> None:
    for event_name in (
        "CreateFunction",
        "DeleteFunction",
        "UpdateFunctionConfiguration",
        "UpdateFunctionCode",
    ):
        payload = _lambda_eventbridge_envelope(event_name)
        assert is_supported_cloudtrail_event(payload) is False


def test_parse_create_function_event() -> None:
    payload = _lambda_eventbridge_envelope(
        "CreateFunction20150331", function_name="my-function"
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.LAMBDA_FUNCTION
    assert parsed.action == CloudTrailEventAction.UPSERT
    assert parsed.identifier == "my-function"
    assert parsed.event_name == "CreateFunction20150331"


def test_parse_update_function_configuration_event() -> None:
    payload = _lambda_eventbridge_envelope("UpdateFunctionConfiguration20150331v2")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.LAMBDA_FUNCTION
    assert parsed.action == CloudTrailEventAction.UPSERT


def test_parse_delete_function_event() -> None:
    payload = _lambda_eventbridge_envelope("DeleteFunction20150331")

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.LAMBDA_FUNCTION
    assert parsed.action == CloudTrailEventAction.DELETE


def test_parse_returns_none_when_function_name_missing() -> None:
    payload = _lambda_eventbridge_envelope("CreateFunction20150331", function_name=None)
    assert parse_cloudtrail_event(payload) is None


def test_is_supported_cloudtrail_event_true_for_versioned_lambda_names() -> None:
    for event_name in (
        "CreateFunction20150331",
        "DeleteFunction20150331",
        "UpdateFunctionConfiguration20150331v2",
        "UpdateFunctionCode20150331v2",
    ):
        payload = _lambda_eventbridge_envelope(event_name)
        assert is_supported_cloudtrail_event(payload) is True


def test_parse_versioned_lambda_event_names() -> None:
    payload = _lambda_eventbridge_envelope(
        "DeleteFunction20150331", function_name="my-function"
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == ObjectKind.LAMBDA_FUNCTION
    assert parsed.action == CloudTrailEventAction.DELETE
    assert parsed.identifier == "my-function"
    assert parsed.event_name == "DeleteFunction20150331"


def test_is_supported_cloudtrail_event_false_for_unrelated_lambda_prefix() -> None:
    payload = _lambda_eventbridge_envelope("GetFunction20150331v2")
    assert is_supported_cloudtrail_event(payload) is False
