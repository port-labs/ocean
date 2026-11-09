from typing import Any, cast

import pytest

from aws.core.helpers.metadata.types import (
    CloudTrailEventAction,
    EventBridgeCloudTrailPayload,
    NormalizedEvent,
)
from aws.core.helpers.types import ObjectKind
from aws.webhook.cloud_control_parser import CLOUD_CONTROL_EVENT_SOURCE
from aws.webhook.cloudtrail_parser import (
    is_supported_cloudtrail_event,
    parse_cloudtrail_event,
)

_ACCOUNT_ID = "111122223333"
_REGION = "us-east-1"


def _cloud_control_event(
    event_name: str,
    *,
    request_parameters: dict[str, Any] | None = None,
    response_elements: dict[str, Any] | None = None,
    event_source: str = CLOUD_CONTROL_EVENT_SOURCE,
) -> EventBridgeCloudTrailPayload:
    detail: dict[str, Any] = {
        "eventName": event_name,
        "eventSource": event_source,
        "awsRegion": _REGION,
        "recipientAccountId": _ACCOUNT_ID,
        "requestParameters": request_parameters or {},
    }
    if response_elements is not None:
        detail["responseElements"] = response_elements
    return cast(
        EventBridgeCloudTrailPayload,
        {"account": _ACCOUNT_ID, "region": _REGION, "detail": detail},
    )


def test_create_resource_uses_progress_event_identifier() -> None:
    payload = _cloud_control_event(
        "CreateResource",
        request_parameters={"typeName": "AWS::Logs::LogGroup"},
        response_elements={
            "progressEvent": {
                "typeName": "AWS::Logs::LogGroup",
                "identifier": "my-log-group",
                "operationStatus": "IN_PROGRESS",
            }
        },
    )

    assert is_supported_cloudtrail_event(payload) is True
    assert parse_cloudtrail_event(payload) == NormalizedEvent(
        kind="AWS::Logs::LogGroup",
        identifier="my-log-group",
        account_id=_ACCOUNT_ID,
        region=_REGION,
        action=CloudTrailEventAction.UPSERT,
        event_name="CreateResource",
    )


@pytest.mark.parametrize(
    ("event_name", "action"),
    [
        ("UpdateResource", CloudTrailEventAction.UPSERT),
        ("DeleteResource", CloudTrailEventAction.DELETE),
    ],
)
def test_update_and_delete_use_request_identifier(
    event_name: str, action: CloudTrailEventAction
) -> None:
    payload = _cloud_control_event(
        event_name,
        request_parameters={"typeName": "AWS::IAM::Role", "identifier": "my-role"},
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == "AWS::IAM::Role"
    assert parsed.identifier == "my-role"
    assert parsed.action == action


def test_accepts_pascal_case_fields() -> None:
    payload = _cloud_control_event(
        "CreateResource",
        response_elements={
            "ProgressEvent": {"TypeName": "AWS::IAM::Role", "Identifier": "my-role"}
        },
    )

    parsed = parse_cloudtrail_event(payload)

    assert parsed is not None
    assert parsed.kind == "AWS::IAM::Role"
    assert parsed.identifier == "my-role"


def test_create_without_identifier_is_skipped() -> None:
    payload = _cloud_control_event(
        "CreateResource",
        request_parameters={"typeName": "AWS::IAM::Role"},
        response_elements={"progressEvent": {"typeName": "AWS::IAM::Role"}},
    )

    assert is_supported_cloudtrail_event(payload) is True
    assert parse_cloudtrail_event(payload) is None


def test_first_class_kind_is_skipped() -> None:
    payload = _cloud_control_event(
        "UpdateResource",
        request_parameters={
            "typeName": ObjectKind.SQS_QUEUE.value,
            "identifier": "https://sqs.us-east-1.amazonaws.com/111122223333/q",
        },
    )

    assert is_supported_cloudtrail_event(payload) is False
    assert parse_cloudtrail_event(payload) is None


@pytest.mark.parametrize(
    "event_name", ["GetResource", "ListResources", "GetResourceRequestStatus"]
)
def test_read_apis_are_skipped(event_name: str) -> None:
    payload = _cloud_control_event(
        event_name,
        request_parameters={"typeName": "AWS::IAM::Role", "identifier": "my-role"},
    )

    assert is_supported_cloudtrail_event(payload) is False
    assert parse_cloudtrail_event(payload) is None


def test_other_event_source_is_skipped() -> None:
    payload = _cloud_control_event(
        "UpdateResource",
        request_parameters={"typeName": "AWS::IAM::Role", "identifier": "my-role"},
        event_source="iam.amazonaws.com",
    )

    assert is_supported_cloudtrail_event(payload) is False


def test_invalid_type_name_is_skipped() -> None:
    payload = _cloud_control_event(
        "UpdateResource",
        request_parameters={"typeName": "Custom::Thing", "identifier": "x"},
    )

    assert is_supported_cloudtrail_event(payload) is False


def test_error_code_is_skipped() -> None:
    payload = _cloud_control_event(
        "DeleteResource",
        request_parameters={"typeName": "AWS::IAM::Role", "identifier": "my-role"},
    )
    payload["detail"]["errorCode"] = "AccessDenied"

    assert is_supported_cloudtrail_event(payload) is False
    assert parse_cloudtrail_event(payload) is None
