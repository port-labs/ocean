from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from aws.core.helpers.types import ObjectKind
from aws.events.s3_bucket_webhook_processor import (
    LIVE_EVENTS_API_KEY_HEADER,
    S3BucketWebhookProcessor,
)

MODULE = "aws.events.s3_bucket_webhook_processor"


def _create_event(bucket_name: str = "my-bucket") -> dict[str, Any]:
    return {
        "account": "111122223333",
        "region": "us-east-1",
        "detail": {
            "eventName": "CreateBucket",
            "awsRegion": "us-east-1",
            "recipientAccountId": "111122223333",
            "requestParameters": {"bucketName": bucket_name},
        },
    }


def _delete_event(bucket_name: str = "my-bucket") -> dict[str, Any]:
    return {
        "account": "111122223333",
        "region": "us-east-1",
        "detail": {
            "eventName": "DeleteBucket",
            "awsRegion": "us-east-1",
            "recipientAccountId": "111122223333",
            "requestParameters": {"bucketName": bucket_name},
        },
    }


@pytest.fixture
def processor() -> S3BucketWebhookProcessor:
    return S3BucketWebhookProcessor(
        WebhookEvent(trace_id="test", payload={}, headers={})
    )


@pytest.mark.asyncio
async def test_should_process_event_true_for_create(
    processor: S3BucketWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="t", payload=_create_event(), headers={})
    assert await processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_should_process_event_false_for_unsupported_event_name(
    processor: S3BucketWebhookProcessor,
) -> None:
    payload = _create_event()
    payload["detail"]["eventName"] = "PutBucketTagging"
    event = WebhookEvent(trace_id="t", payload=payload, headers={})
    assert await processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_get_matching_kinds_returns_s3_bucket(
    processor: S3BucketWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="t", payload=_create_event(), headers={})
    assert await processor.get_matching_kinds(event) == [ObjectKind.S3_BUCKET]


@pytest.mark.asyncio
async def test_authenticate_succeeds_with_matching_api_key(
    processor: S3BucketWebhookProcessor,
) -> None:
    with patch(f"{MODULE}.ocean") as mock_ocean:
        mock_ocean.integration_config = {"live_events_api_key": "secret"}
        result = await processor.authenticate(
            {}, {LIVE_EVENTS_API_KEY_HEADER: "secret"}
        )
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_fails_with_wrong_api_key(
    processor: S3BucketWebhookProcessor,
) -> None:
    with patch(f"{MODULE}.ocean") as mock_ocean:
        mock_ocean.integration_config = {"live_events_api_key": "secret"}
        result = await processor.authenticate({}, {LIVE_EVENTS_API_KEY_HEADER: "wrong"})
    assert result is False


@pytest.mark.asyncio
async def test_authenticate_fails_when_not_configured(
    processor: S3BucketWebhookProcessor,
) -> None:
    with patch(f"{MODULE}.ocean") as mock_ocean:
        mock_ocean.integration_config = {}
        result = await processor.authenticate(
            {}, {LIVE_EVENTS_API_KEY_HEADER: "anything"}
        )
    assert result is False


@pytest.mark.asyncio
async def test_validate_payload_true_for_supported_event(
    processor: S3BucketWebhookProcessor,
) -> None:
    assert await processor.validate_payload(_create_event()) is True


@pytest.mark.asyncio
async def test_validate_payload_false_for_malformed_payload(
    processor: S3BucketWebhookProcessor,
) -> None:
    assert await processor.validate_payload({}) is False


@pytest.mark.asyncio
async def test_handle_event_delete_returns_deleted_result(
    processor: S3BucketWebhookProcessor,
) -> None:
    result = await processor.handle_event(_delete_event("bucket-to-delete"), None)  # type: ignore[arg-type]

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [
        {
            "Type": ObjectKind.S3_BUCKET,
            "Properties": {
                "Arn": "arn:aws:s3:::bucket-to-delete",
                "BucketName": "bucket-to-delete",
            },
        }
    ]


@pytest.mark.asyncio
async def test_handle_event_create_fetches_and_returns_resource(
    processor: S3BucketWebhookProcessor,
) -> None:
    fake_resource = {
        "Type": ObjectKind.S3_BUCKET,
        "Properties": {"BucketName": "my-bucket"},
    }

    with (
        patch(
            f"{MODULE}.get_session_for_account", new=AsyncMock(return_value="session")
        ),
        patch(f"{MODULE}.S3BucketExporter") as mock_exporter_cls,
    ):
        mock_exporter = mock_exporter_cls.return_value
        mock_exporter.get_resource = AsyncMock(return_value=fake_resource)

        result = await processor.handle_event(_create_event(), None)  # type: ignore[arg-type]

    mock_exporter_cls.assert_called_once_with("session")
    assert result.updated_raw_results == [fake_resource]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_create_skips_when_no_session_found(
    processor: S3BucketWebhookProcessor,
) -> None:
    with patch(f"{MODULE}.get_session_for_account", new=AsyncMock(return_value=None)):
        result = await processor.handle_event(_create_event(), None)  # type: ignore[arg-type]

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_create_treats_access_denied_as_deleted(
    processor: S3BucketWebhookProcessor,
) -> None:
    class FakeAccessDenied(Exception):
        response = {"Error": {"Code": "AccessDenied"}}

    with (
        patch(
            f"{MODULE}.get_session_for_account", new=AsyncMock(return_value="session")
        ),
        patch(f"{MODULE}.S3BucketExporter") as mock_exporter_cls,
    ):
        mock_exporter = mock_exporter_cls.return_value
        mock_exporter.get_resource = AsyncMock(side_effect=FakeAccessDenied())

        result = await processor.handle_event(_create_event("denied-bucket"), None)  # type: ignore[arg-type]

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [
        {
            "Type": ObjectKind.S3_BUCKET,
            "Properties": {
                "Arn": "arn:aws:s3:::denied-bucket",
                "BucketName": "denied-bucket",
            },
        }
    ]
