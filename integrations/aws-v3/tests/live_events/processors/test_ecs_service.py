"""Tests for EcsServiceLiveEventProcessor — deployment and scaling upsert."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiobotocore.session import AioSession

from aws.live_events.processors.ecs_service import EcsServiceLiveEventProcessor
from tests.live_events.conftest import make_eventbridge_event

_ACCOUNT = "123456789012"
_REGION = "ap-southeast-1"
_CLUSTER_ARN = f"arn:aws:ecs:{_REGION}:{_ACCOUNT}:cluster/prod-cluster"
_SERVICE_ARN = f"arn:aws:ecs:{_REGION}:{_ACCOUNT}:service/prod-cluster/api-service"


def _ecs_event(detail_type: str, cluster_arn: str = _CLUSTER_ARN, service_arn: str = _SERVICE_ARN) -> dict:
    return make_eventbridge_event(
        detail_type,
        {
            "clusterArn": cluster_arn,
            "serviceArn": service_arn,
            "eventType": "INFO",
        },
        account=_ACCOUNT,
        region=_REGION,
        source="aws.ecs",
    )


@pytest.fixture
def processor() -> EcsServiceLiveEventProcessor:
    return EcsServiceLiveEventProcessor()


@pytest.fixture
def mock_session() -> AioSession:
    return MagicMock(spec=AioSession)


class TestEcsServiceLiveEventProcessor:
    # -----------------------------------------------------------------------
    # can_handle
    # -----------------------------------------------------------------------

    def test_can_handle_deployment_state_change(self, processor: EcsServiceLiveEventProcessor) -> None:
        assert processor.can_handle("ECS Deployment State Change", {}) is True

    def test_can_handle_service_action(self, processor: EcsServiceLiveEventProcessor) -> None:
        assert processor.can_handle("ECS Service Action", {}) is True

    def test_cannot_handle_ec2_event(self, processor: EcsServiceLiveEventProcessor) -> None:
        assert processor.can_handle("EC2 Instance State-change Notification", {}) is False

    # -----------------------------------------------------------------------
    # Deployment state change → upsert
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_deployment_state_change_upserts(
        self, processor: EcsServiceLiveEventProcessor, mock_session: AioSession
    ) -> None:
        fake_resource = {
            "Type": "AWS::ECS::Service",
            "Properties": {
                "ServiceName": "api-service",
                "ClusterArn": _CLUSTER_ARN,
                "Status": "ACTIVE",
            },
        }

        with patch(
            "aws.live_events.processors.ecs_service.EcsServiceExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = AsyncMock(return_value=fake_resource)

            event = _ecs_event("ECS Deployment State Change")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert result.updated_raw_results == [fake_resource]
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_service_action_upserts(
        self, processor: EcsServiceLiveEventProcessor, mock_session: AioSession
    ) -> None:
        fake_resource = {
            "Type": "AWS::ECS::Service",
            "Properties": {"ServiceName": "api-service"},
        }

        with patch(
            "aws.live_events.processors.ecs_service.EcsServiceExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = AsyncMock(return_value=fake_resource)

            event = _ecs_event("ECS Service Action")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert result.updated_raw_results == [fake_resource]
        assert result.deleted_raw_results == []

    # -----------------------------------------------------------------------
    # ARN extraction
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_cluster_and_service_names_extracted_from_arns(
        self, processor: EcsServiceLiveEventProcessor, mock_session: AioSession
    ) -> None:
        captured_options = {}

        async def _capture_get_resource(options):
            captured_options["cluster_name"] = options.cluster_name
            captured_options["service_name"] = options.service_name
            return {"Type": "AWS::ECS::Service", "Properties": {}}

        with patch(
            "aws.live_events.processors.ecs_service.EcsServiceExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = _capture_get_resource

            event = _ecs_event("ECS Deployment State Change")
            await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert captured_options["cluster_name"] == "prod-cluster"
        assert captured_options["service_name"] == "api-service"

    # -----------------------------------------------------------------------
    # Resilience
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_missing_arns_returns_empty(
        self, processor: EcsServiceLiveEventProcessor, mock_session: AioSession
    ) -> None:
        event = make_eventbridge_event(
            "ECS Deployment State Change",
            {"eventType": "INFO"},  # no clusterArn or serviceArn
        )
        result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_exporter_exception_returns_empty(
        self, processor: EcsServiceLiveEventProcessor, mock_session: AioSession
    ) -> None:
        with patch(
            "aws.live_events.processors.ecs_service.EcsServiceExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = AsyncMock(
                side_effect=Exception("ECS cluster not found")
            )

            event = _ecs_event("ECS Deployment State Change")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
