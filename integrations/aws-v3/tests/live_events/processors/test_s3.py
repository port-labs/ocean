"""Tests for S3LiveEventProcessor — delete correctness and upsert."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiobotocore.session import AioSession

from aws.live_events.processors.s3 import S3LiveEventProcessor
from tests.live_events.conftest import make_eventbridge_event

_ACCOUNT = "123456789012"
_REGION = "us-east-1"
_DETAIL_TYPE = "AWS API Call via CloudTrail"


def _s3_event(event_name: str, bucket_name: str) -> dict:
    return make_eventbridge_event(
        _DETAIL_TYPE,
        {
            "eventSource": "s3.amazonaws.com",
            "eventName": event_name,
            "requestParameters": {"bucketName": bucket_name},
        },
        account=_ACCOUNT,
        region=_REGION,
        source="aws.cloudtrail",
    )


@pytest.fixture
def processor() -> S3LiveEventProcessor:
    return S3LiveEventProcessor()


@pytest.fixture
def mock_session() -> AioSession:
    return MagicMock(spec=AioSession)


class TestS3LiveEventProcessor:
    # -----------------------------------------------------------------------
    # can_handle
    # -----------------------------------------------------------------------

    def test_can_handle_create_bucket(self, processor: S3LiveEventProcessor) -> None:
        detail = {"eventSource": "s3.amazonaws.com", "eventName": "CreateBucket"}
        assert processor.can_handle(_DETAIL_TYPE, detail) is True

    def test_can_handle_delete_bucket(self, processor: S3LiveEventProcessor) -> None:
        detail = {"eventSource": "s3.amazonaws.com", "eventName": "DeleteBucket"}
        assert processor.can_handle(_DETAIL_TYPE, detail) is True

    def test_cannot_handle_other_s3_event(self, processor: S3LiveEventProcessor) -> None:
        detail = {"eventSource": "s3.amazonaws.com", "eventName": "PutBucketPolicy"}
        assert processor.can_handle(_DETAIL_TYPE, detail) is False

    def test_cannot_handle_non_s3_source(self, processor: S3LiveEventProcessor) -> None:
        detail = {"eventSource": "ec2.amazonaws.com", "eventName": "CreateBucket"}
        assert processor.can_handle(_DETAIL_TYPE, detail) is False

    # -----------------------------------------------------------------------
    # S3 deleted → delete correctness
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_s3_deleted_returns_delete_result(
        self, processor: S3LiveEventProcessor, mock_session: AioSession
    ) -> None:
        with patch("aws.live_events.processors.s3.S3BucketExporter") as MockExporter:
            event = _s3_event("DeleteBucket", "my-deleted-bucket")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)
            # Exporter should NOT be called on delete
            MockExporter.return_value.get_resource.assert_not_called()

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["Properties"]["BucketName"] == "my-deleted-bucket"

    # -----------------------------------------------------------------------
    # S3 created → upsert correctness
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_s3_created_upserts_resource(
        self, processor: S3LiveEventProcessor, mock_session: AioSession
    ) -> None:
        fake_resource = {
            "Type": "AWS::S3::Bucket",
            "Properties": {"BucketName": "new-bucket", "Arn": "arn:aws:s3:::new-bucket"},
        }

        with patch(
            "aws.live_events.processors.s3.S3BucketExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = AsyncMock(return_value=fake_resource)

            event = _s3_event("CreateBucket", "new-bucket")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert result.updated_raw_results == [fake_resource]
        assert result.deleted_raw_results == []

    # -----------------------------------------------------------------------
    # Resilience
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_missing_bucket_name_returns_empty(
        self, processor: S3LiveEventProcessor, mock_session: AioSession
    ) -> None:
        event = make_eventbridge_event(
            _DETAIL_TYPE,
            {"eventSource": "s3.amazonaws.com", "eventName": "CreateBucket", "requestParameters": {}},
        )
        result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_exporter_exception_returns_empty(
        self, processor: S3LiveEventProcessor, mock_session: AioSession
    ) -> None:
        with patch(
            "aws.live_events.processors.s3.S3BucketExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = AsyncMock(
                side_effect=Exception("S3 bucket not accessible")
            )

            event = _s3_event("CreateBucket", "err-bucket")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
