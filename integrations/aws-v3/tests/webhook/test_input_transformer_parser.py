from typing import Any, cast

import pytest

from aws.core.helpers.metadata.types import CloudTrailEventAction, NormalizedEvent
from aws.webhook.input_transformer_parser import (
    InputTransformerPayload,
    is_input_transformer_event,
    parse_input_transformer_event,
)


def _payload(**overrides: Any) -> InputTransformerPayload:
    payload: dict[str, Any] = {
        "resource_type": "AWS::IAM::Role",
        "identifier": "my-role",
        "accountId": "111122223333",
        "awsRegion": "us-east-1",
        "eventName": "CreateRole",
    }
    payload.update(overrides)
    return cast(InputTransformerPayload, payload)


def test_is_input_transformer_event_true_for_transformed_payload() -> None:
    assert is_input_transformer_event(_payload()) is True


def test_is_input_transformer_event_false_for_raw_cloudtrail_payload() -> None:
    payload = cast(
        InputTransformerPayload,
        {"account": "111122223333", "detail": {"eventName": "CreateRole"}},
    )
    assert is_input_transformer_event(payload) is False


def test_is_input_transformer_event_false_when_detail_present() -> None:
    payload = _payload(detail={"eventName": "CreateRole"})
    assert is_input_transformer_event(payload) is False


def test_is_input_transformer_event_false_when_required_fields_missing() -> None:
    assert is_input_transformer_event(cast(InputTransformerPayload, {"resource_type": "AWS::IAM::Role"})) is False


def test_parse_input_transformer_event_returns_upsert() -> None:
    assert parse_input_transformer_event(_payload()) == NormalizedEvent(
        kind="AWS::IAM::Role",
        identifier="my-role",
        account_id="111122223333",
        region="us-east-1",
        action=CloudTrailEventAction.UPSERT,
        event_name="CreateRole",
    )


def test_parse_input_transformer_event_defaults_event_name() -> None:
    payload = _payload()
    del payload["eventName"]

    parsed = parse_input_transformer_event(payload)

    assert parsed is not None
    assert parsed.event_name == ""


@pytest.mark.parametrize(
    "missing_field", ["resource_type", "identifier", "accountId", "awsRegion"]
)
def test_parse_input_transformer_event_returns_none_when_field_missing(
    missing_field: str,
) -> None:
    payload = _payload(**{missing_field: ""})
    assert parse_input_transformer_event(payload) is None
