from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.webhook.processors.s3_bucket import S3BucketWebhookProcessor
from tests.webhook.conftest import make_sns_notification, make_webhook_event


def _envelope(event_name: str, bucket: str = "port-test-bucket") -> dict:
    return {
        "version": "0",
        "id": "ev-1",
        "detail-type": "AWS API Call via CloudTrail",
        "source": "aws.s3",
        "account": "111111111111",
        "time": "2026-05-14T12:00:00Z",
        "region": "us-east-1",
        "detail": {
            "eventSource": "s3.amazonaws.com",
            "eventName": event_name,
            "requestParameters": {"bucketName": bucket},
        },
    }


@pytest.mark.asyncio
async def test_create_bucket_triggers_upsert(stub_session_resolver) -> None:
    payload = make_sns_notification(_envelope("CreateBucket"))
    event = make_webhook_event(payload)
    processor = S3BucketWebhookProcessor(event=event)

    assert await processor.should_process_event(event) is True

    mock_exporter = AsyncMock()
    mock_exporter.get_resource = AsyncMock(
        return_value={"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "port-test-bucket"}}
    )
    with patch(
        "aws.webhook.processors.s3_bucket.S3BucketWebhookProcessor.exporter_cls",
        return_value=mock_exporter,
    ):
        result = await processor.handle_event(payload, resource=None)

    assert len(result.updated_raw_results) == 1
    assert result.deleted_raw_results == []
    request = mock_exporter.get_resource.call_args.args[0]
    assert isinstance(request, SingleBucketRequest)
    assert request.bucket_name == "port-test-bucket"


@pytest.mark.asyncio
async def test_delete_bucket_triggers_delete(stub_session_resolver) -> None:
    payload = make_sns_notification(_envelope("DeleteBucket"))
    event = make_webhook_event(payload)
    processor = S3BucketWebhookProcessor(event=event)

    result = await processor.handle_event(payload, resource=None)

    assert result.updated_raw_results == []
    assert len(result.deleted_raw_results) == 1
    assert result.deleted_raw_results[0]["Properties"]["BucketName"] == "port-test-bucket"


@pytest.mark.asyncio
async def test_unrelated_eventname_skipped(stub_session_resolver) -> None:
    # `GetObject` etc. shouldn't trigger a bucket upsert.
    payload = make_sns_notification(_envelope("GetObject"))
    event = make_webhook_event(payload)
    processor = S3BucketWebhookProcessor(event=event)

    result = await processor.handle_event(payload, resource=None)
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_non_s3_event_source_does_not_match(stub_session_resolver) -> None:
    envelope = _envelope("CreateBucket")
    envelope["detail"]["eventSource"] = "ec2.amazonaws.com"
    payload = make_sns_notification(envelope)
    event = make_webhook_event(payload)
    processor = S3BucketWebhookProcessor(event=event)

    assert await processor.should_process_event(event) is False
