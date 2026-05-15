"""Tests for `S3BucketWebhookProcessor`."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws.webhook.webhook_processors.s3_bucket_webhook_processor import (
    S3BucketWebhookProcessor,
    _resolve_bucket_region,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from tests.webhook.fixtures import s3_create_bucket_event, s3_delete_bucket_event


def _processor_for(payload: dict[str, Any]) -> S3BucketWebhookProcessor:
    event = WebhookEvent(trace_id="t", payload=payload, headers={})
    return S3BucketWebhookProcessor(event=event)


def _resource_config() -> MagicMock:
    config = MagicMock()
    config.selector.include_actions = []
    return config


class TestResolveBucketRegion:
    def test_returns_location_constraint_when_present(self) -> None:
        detail = {
            "requestParameters": {
                "CreateBucketConfiguration": {"LocationConstraint": "eu-west-1"}
            }
        }
        assert _resolve_bucket_region(detail) == "eu-west-1"

    def test_defaults_to_us_east_1_when_constraint_absent(self) -> None:
        detail = {"requestParameters": {"bucketName": "foo"}}
        assert _resolve_bucket_region(detail) == "us-east-1"

    def test_defaults_to_us_east_1_when_constraint_is_empty_string(self) -> None:
        detail = {
            "requestParameters": {
                "CreateBucketConfiguration": {"LocationConstraint": "   "}
            }
        }
        assert _resolve_bucket_region(detail) == "us-east-1"


class TestMatchesEvent:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("event_name", ["CreateBucket", "DeleteBucket"])
    async def test_matches_create_and_delete(self, event_name: str) -> None:
        payload = (
            s3_create_bucket_event("b")
            if event_name == "CreateBucket"
            else s3_delete_bucket_event("b")
        )
        processor = _processor_for(payload)
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        assert await processor._matches_event(event) is True

    @pytest.mark.asyncio
    async def test_does_not_match_object_put(self) -> None:
        payload = s3_create_bucket_event("b")
        payload["detail"]["eventName"] = "PutObject"
        processor = _processor_for(payload)
        event = WebhookEvent(trace_id="t", payload=payload, headers={})

        assert await processor._matches_event(event) is False


class TestHandleEvent:
    @pytest.mark.asyncio
    async def test_delete_bucket_emits_delete(self) -> None:
        payload = s3_delete_bucket_event("my-bucket")
        processor = _processor_for(payload)

        result = await processor.handle_event(
            payload=payload, resource_config=_resource_config()
        )

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        deleted = result.deleted_raw_results[0]
        assert deleted["Properties"]["BucketName"] == "my-bucket"
        assert deleted["Properties"]["Arn"] == "arn:aws:s3:::my-bucket"

    @pytest.mark.asyncio
    async def test_create_bucket_uses_location_constraint_region(self) -> None:
        payload = s3_create_bucket_event("my-bucket", location_constraint="eu-west-1")
        processor = _processor_for(payload)
        resource = {
            "Type": "AWS::S3::Bucket",
            "Properties": {"BucketName": "my-bucket"},
        }

        with patch(
            "aws.webhook.webhook_processors.s3_bucket_webhook_processor.session_for_account",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "aws.webhook.webhook_processors.s3_bucket_webhook_processor.S3BucketExporter"
            ) as ExporterCls:
                ExporterCls.return_value.get_resource = AsyncMock(return_value=resource)

                result = await processor.handle_event(
                    payload=payload, resource_config=_resource_config()
                )

                request = ExporterCls.return_value.get_resource.call_args.args[0]

        assert result.updated_raw_results == [resource]
        assert request.region == "eu-west-1"
        assert request.bucket_name == "my-bucket"

    @pytest.mark.asyncio
    async def test_create_bucket_defaults_region_to_us_east_1(self) -> None:
        payload = s3_create_bucket_event("my-bucket", location_constraint=None)
        processor = _processor_for(payload)

        with patch(
            "aws.webhook.webhook_processors.s3_bucket_webhook_processor.session_for_account",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "aws.webhook.webhook_processors.s3_bucket_webhook_processor.S3BucketExporter"
            ) as ExporterCls:
                ExporterCls.return_value.get_resource = AsyncMock(return_value={"x": 1})

                await processor.handle_event(
                    payload=payload, resource_config=_resource_config()
                )

                request = ExporterCls.return_value.get_resource.call_args.args[0]

        assert request.region == "us-east-1"

    @pytest.mark.asyncio
    async def test_resource_not_found_converts_to_delete(self) -> None:
        payload = s3_create_bucket_event("my-bucket")
        processor = _processor_for(payload)

        class _NotFound(Exception):
            response = {"Error": {"Code": "ResourceNotFoundException"}}

        with patch(
            "aws.webhook.webhook_processors.s3_bucket_webhook_processor.session_for_account",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "aws.webhook.webhook_processors.s3_bucket_webhook_processor.S3BucketExporter"
            ) as ExporterCls:
                ExporterCls.return_value.get_resource = AsyncMock(
                    side_effect=_NotFound()
                )

                result = await processor.handle_event(
                    payload=payload, resource_config=_resource_config()
                )

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1

    @pytest.mark.asyncio
    async def test_drops_when_bucket_name_missing(self) -> None:
        payload = s3_create_bucket_event("b")
        del payload["detail"]["requestParameters"]["bucketName"]
        processor = _processor_for(payload)

        result = await processor.handle_event(
            payload=payload, resource_config=_resource_config()
        )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
