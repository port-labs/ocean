from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from aws.core.helpers.types import ObjectKind
from aws.webhook.consts import LIVE_EVENTS_API_KEY_HEADER
from aws.webhook.webhook_processors.cloudtrail_webhook_processor import (
    CloudTrailWebhookProcessor,
)

MODULE = "aws.webhook.webhook_processors.cloudtrail_webhook_processor"


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
def processor() -> CloudTrailWebhookProcessor:
    return CloudTrailWebhookProcessor(
        WebhookEvent(trace_id="test", payload={}, headers={})
    )


@pytest.mark.asyncio
async def test_should_process_event_true_for_create(
    processor: CloudTrailWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="t", payload=_create_event(), headers={})
    assert await processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_should_process_event_false_for_unsupported_event_name(
    processor: CloudTrailWebhookProcessor,
) -> None:
    payload = _create_event()
    payload["detail"]["eventName"] = "PutBucketTagging"
    event = WebhookEvent(trace_id="t", payload=payload, headers={})
    assert await processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_get_matching_kinds_returns_s3_bucket(
    processor: CloudTrailWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="t", payload=_create_event(), headers={})
    assert await processor.get_matching_kinds(event) == [ObjectKind.S3_BUCKET]


@pytest.mark.asyncio
async def test_authenticate_succeeds_with_matching_api_key(
    processor: CloudTrailWebhookProcessor,
) -> None:
    with patch(
        "aws.webhook.webhook_processors.base_webhook_processor.ocean"
    ) as mock_ocean:
        mock_ocean.integration_config = {"live_events_api_key": "secret"}
        result = await processor.authenticate(
            {}, {LIVE_EVENTS_API_KEY_HEADER: "secret"}
        )
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_fails_with_wrong_api_key(
    processor: CloudTrailWebhookProcessor,
) -> None:
    with patch(
        "aws.webhook.webhook_processors.base_webhook_processor.ocean"
    ) as mock_ocean:
        mock_ocean.integration_config = {"live_events_api_key": "secret"}
        result = await processor.authenticate({}, {LIVE_EVENTS_API_KEY_HEADER: "wrong"})
    assert result is False


@pytest.mark.asyncio
async def test_authenticate_fails_when_not_configured(
    processor: CloudTrailWebhookProcessor,
) -> None:
    with patch(
        "aws.webhook.webhook_processors.base_webhook_processor.ocean"
    ) as mock_ocean:
        mock_ocean.integration_config = {}
        result = await processor.authenticate(
            {}, {LIVE_EVENTS_API_KEY_HEADER: "anything"}
        )
    assert result is False


@pytest.mark.asyncio
async def test_validate_payload_true_for_supported_event(
    processor: CloudTrailWebhookProcessor,
) -> None:
    assert await processor.validate_payload(_create_event()) is True


@pytest.mark.asyncio
async def test_validate_payload_false_for_malformed_payload(
    processor: CloudTrailWebhookProcessor,
) -> None:
    assert await processor.validate_payload({}) is False


@pytest.mark.asyncio
async def test_handle_event_delete_returns_deleted_result(
    processor: CloudTrailWebhookProcessor,
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
    processor: CloudTrailWebhookProcessor,
) -> None:
    fake_resource = {
        "Type": ObjectKind.S3_BUCKET,
        "Properties": {"BucketName": "my-bucket"},
    }

    with (
        patch(
            f"{MODULE}.get_session_for_account", new=AsyncMock(return_value="session")
        ),
        patch(f"{MODULE}.EXPORTER_REGISTRY") as mock_registry,
    ):
        mock_exporter = AsyncMock()
        mock_exporter.get_resource = AsyncMock(return_value=fake_resource)
        mock_registry.get.return_value.exporter_cls.return_value = mock_exporter

        result = await processor.handle_event(_create_event(), None)  # type: ignore[arg-type]

    mock_registry.get.return_value.exporter_cls.assert_called_once_with("session")
    assert result.updated_raw_results == [fake_resource]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_create_skips_when_no_session_found(
    processor: CloudTrailWebhookProcessor,
) -> None:
    with patch(f"{MODULE}.get_session_for_account", new=AsyncMock(return_value=None)):
        result = await processor.handle_event(_create_event(), None)  # type: ignore[arg-type]

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_create_treats_access_denied_as_deleted(
    processor: CloudTrailWebhookProcessor,
) -> None:
    class FakeAccessDenied(Exception):
        response = {"Error": {"Code": "AccessDenied"}}

    with (
        patch(
            f"{MODULE}.get_session_for_account", new=AsyncMock(return_value="session")
        ),
        patch(f"{MODULE}.EXPORTER_REGISTRY") as mock_registry,
    ):
        mock_exporter = AsyncMock()
        mock_exporter.get_resource = AsyncMock(side_effect=FakeAccessDenied())
        mock_binding = mock_registry.get.return_value
        mock_binding.exporter_cls.return_value = mock_exporter
        mock_binding.delete_properties_factory.return_value = {
            "Arn": "arn:aws:s3:::denied-bucket",
            "BucketName": "denied-bucket",
        }

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
