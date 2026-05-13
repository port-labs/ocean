import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from aws.live_events.handlers.s3 import S3BucketLiveEventHandler
from aws.live_events.handlers.lambda_function import LambdaFunctionLiveEventHandler
from aws.live_events.handlers.ecs import ECSServiceLiveEventHandler


# ── S3 ──────────────────────────────────────────────────────────────────────

def _s3_event(event_name: str, bucket_name: str) -> dict[str, Any]:
    return {
        "source": "aws.s3",
        "detail-type": "AWS API Call via CloudTrail",
        "account": "123456789012",
        "region": "us-east-1",
        "detail": {
            "eventName": event_name,
            "requestParameters": {"bucketName": bucket_name},
        },
    }


class TestS3BucketLiveEventHandler:

    @pytest.fixture
    def handler(self) -> S3BucketLiveEventHandler:
        return S3BucketLiveEventHandler(AsyncMock())

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.s3.S3BucketExporter")
    async def test_create_bucket_triggers_upsert(
        self, mock_exporter_cls: MagicMock, handler: S3BucketLiveEventHandler
    ) -> None:
        """CreateBucket event should fetch and upsert the bucket."""
        mock_exporter = AsyncMock()
        mock_exporter_cls.return_value = mock_exporter
        mock_exporter.get_resource.return_value = {
            "Type": "AWS::S3::Bucket",
            "Properties": {"BucketName": "my-new-bucket"},
        }

        event = _s3_event("CreateBucket", "my-new-bucket")

        with patch.object(handler, "_upsert", new_callable=AsyncMock) as mock_upsert:
            await handler.handle(event, account_id="123456789012", region="us-east-1")
            mock_upsert.assert_called_once()

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.s3.S3BucketExporter")
    async def test_delete_bucket_triggers_delete(
        self, mock_exporter_cls: MagicMock, handler: S3BucketLiveEventHandler
    ) -> None:
        """DeleteBucket event should delete the entity from Port."""
        event = _s3_event("DeleteBucket", "my-old-bucket")

        with patch.object(handler, "_delete", new_callable=AsyncMock) as mock_delete:
            await handler.handle(event, account_id="123456789012", region="us-east-1")
            mock_delete.assert_called_once_with("my-old-bucket")
            mock_exporter_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_bucket_name_skipped(
        self, handler: S3BucketLiveEventHandler
    ) -> None:
        event = {
            "source": "aws.s3",
            "detail-type": "AWS API Call via CloudTrail",
            "account": "123456789012",
            "region": "us-east-1",
            "detail": {"eventName": "CreateBucket", "requestParameters": {}},
        }

        with patch.object(handler, "_upsert", new_callable=AsyncMock) as mock_upsert:
            with patch.object(handler, "_delete", new_callable=AsyncMock) as mock_delete:
                await handler.handle(event, "123456789012", "us-east-1")
                mock_upsert.assert_not_called()
                mock_delete.assert_not_called()


# ── Lambda ───────────────────────────────────────────────────────────────────

def _lambda_event(event_name: str, function_name: str) -> dict[str, Any]:
    return {
        "source": "aws.lambda",
        "detail-type": "AWS API Call via CloudTrail",
        "account": "123456789012",
        "region": "us-east-1",
        "detail": {
            "eventName": event_name,
            "requestParameters": {"functionName": function_name},
        },
    }


class TestLambdaFunctionLiveEventHandler:

    @pytest.fixture
    def handler(self) -> LambdaFunctionLiveEventHandler:
        return LambdaFunctionLiveEventHandler(AsyncMock())

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.lambda_function.LambdaFunctionExporter")
    async def test_update_function_code_triggers_upsert(
        self, mock_exporter_cls: MagicMock, handler: LambdaFunctionLiveEventHandler
    ) -> None:
        """UpdateFunctionCode event should fetch and upsert the function."""
        mock_exporter = AsyncMock()
        mock_exporter_cls.return_value = mock_exporter
        mock_exporter.get_resource.return_value = {
            "Type": "AWS::Lambda::Function",
            "Properties": {"FunctionName": "my-fn"},
        }

        event = _lambda_event("UpdateFunctionCode20150331v2", "my-fn")

        with patch.object(handler, "_upsert", new_callable=AsyncMock) as mock_upsert:
            await handler.handle(event, "123456789012", "us-east-1")
            mock_upsert.assert_called_once()

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.lambda_function.LambdaFunctionExporter")
    async def test_delete_function_triggers_delete(
        self, mock_exporter_cls: MagicMock, handler: LambdaFunctionLiveEventHandler
    ) -> None:
        """DeleteFunction event should delete the entity from Port."""
        event = _lambda_event("DeleteFunction20150331", "my-fn")

        with patch.object(handler, "_delete", new_callable=AsyncMock) as mock_delete:
            await handler.handle(event, "123456789012", "us-east-1")
            mock_delete.assert_called_once_with("my-fn")
            mock_exporter_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_event_name_skipped(
        self, handler: LambdaFunctionLiveEventHandler
    ) -> None:
        """An unrecognised Lambda eventName should be silently skipped."""
        event = _lambda_event("ListFunctions", "my-fn")

        with patch.object(handler, "_upsert", new_callable=AsyncMock) as mock_upsert:
            with patch.object(handler, "_delete", new_callable=AsyncMock) as mock_delete:
                await handler.handle(event, "123456789012", "us-east-1")
                mock_upsert.assert_not_called()
                mock_delete.assert_not_called()


# ── ECS ──────────────────────────────────────────────────────────────────────

def _ecs_event(detail_type: str, cluster_arn: str, service_arn: str) -> dict[str, Any]:
    return {
        "source": "aws.ecs",
        "detail-type": detail_type,
        "account": "123456789012",
        "region": "us-east-1",
        "detail": {
            "clusterArn": cluster_arn,
            "serviceArn": service_arn,
        },
    }


class TestECSServiceLiveEventHandler:

    @pytest.fixture
    def handler(self) -> ECSServiceLiveEventHandler:
        return ECSServiceLiveEventHandler(AsyncMock())

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.ecs.EcsServiceExporter")
    async def test_deployment_state_change_triggers_upsert(
        self, mock_exporter_cls: MagicMock, handler: ECSServiceLiveEventHandler
    ) -> None:
        """ECS Deployment State Change should fetch and upsert the service."""
        mock_exporter = AsyncMock()
        mock_exporter_cls.return_value = mock_exporter
        mock_exporter.get_resource.return_value = {
            "Type": "AWS::ECS::Service",
            "Properties": {"ServiceName": "my-svc"},
        }

        event = _ecs_event(
            "ECS Deployment State Change",
            "arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster",
            "arn:aws:ecs:us-east-1:123456789012:service/my-cluster/my-svc",
        )

        with patch.object(handler, "_upsert", new_callable=AsyncMock) as mock_upsert:
            await handler.handle(event, "123456789012", "us-east-1")
            mock_upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_arns_skipped(
        self, handler: ECSServiceLiveEventHandler
    ) -> None:
        """Events without clusterArn or serviceArn should be skipped."""
        event = {
            "source": "aws.ecs",
            "detail-type": "ECS Service Action",
            "account": "123456789012",
            "region": "us-east-1",
            "detail": {},
        }

        with patch.object(handler, "_upsert", new_callable=AsyncMock) as mock_upsert:
            with patch.object(handler, "_delete", new_callable=AsyncMock) as mock_delete:
                await handler.handle(event, "123456789012", "us-east-1")
                mock_upsert.assert_not_called()
                mock_delete.assert_not_called()
