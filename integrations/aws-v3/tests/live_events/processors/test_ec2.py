"""Tests for EC2LiveEventProcessor — upsert and delete correctness."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiobotocore.session import AioSession

from aws.live_events.processors.ec2 import EC2LiveEventProcessor
from tests.live_events.conftest import make_eventbridge_event

_ACCOUNT = "123456789012"
_REGION = "us-east-1"
_DETAIL_TYPE = "EC2 Instance State-change Notification"


def _ec2_event(instance_id: str, state: str) -> dict:
    return make_eventbridge_event(
        _DETAIL_TYPE,
        {"instance-id": instance_id, "state": state},
        account=_ACCOUNT,
        region=_REGION,
    )


@pytest.fixture
def processor() -> EC2LiveEventProcessor:
    return EC2LiveEventProcessor()


@pytest.fixture
def mock_session() -> AioSession:
    return MagicMock(spec=AioSession)


class TestEC2LiveEventProcessor:
    # -----------------------------------------------------------------------
    # can_handle
    # -----------------------------------------------------------------------

    def test_can_handle_ec2_state_change(self, processor: EC2LiveEventProcessor) -> None:
        assert processor.can_handle(_DETAIL_TYPE, {}) is True

    def test_cannot_handle_other_detail_type(self, processor: EC2LiveEventProcessor) -> None:
        assert processor.can_handle("ECS Deployment State Change", {}) is False

    # -----------------------------------------------------------------------
    # EC2 running → upsert correctness
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ec2_running_upserts_resource(
        self, processor: EC2LiveEventProcessor, mock_session: AioSession
    ) -> None:
        fake_resource = {
            "Type": "AWS::EC2::Instance",
            "Properties": {"InstanceId": "i-running01", "State": {"Name": "running"}},
        }

        with patch(
            "aws.live_events.processors.ec2.EC2InstanceExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = AsyncMock(return_value=fake_resource)

            event = _ec2_event("i-running01", "running")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert result.updated_raw_results == [fake_resource]
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_ec2_stopped_upserts_resource(
        self, processor: EC2LiveEventProcessor, mock_session: AioSession
    ) -> None:
        """Stopped (not terminated) instances should still be upserted."""
        fake_resource = {
            "Type": "AWS::EC2::Instance",
            "Properties": {"InstanceId": "i-stopped01", "State": {"Name": "stopped"}},
        }

        with patch(
            "aws.live_events.processors.ec2.EC2InstanceExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = AsyncMock(return_value=fake_resource)

            event = _ec2_event("i-stopped01", "stopped")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert result.updated_raw_results == [fake_resource]
        assert result.deleted_raw_results == []

    # -----------------------------------------------------------------------
    # EC2 terminated → delete correctness
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ec2_terminated_deletes_resource(
        self, processor: EC2LiveEventProcessor, mock_session: AioSession
    ) -> None:
        with patch(
            "aws.live_events.processors.ec2.EC2InstanceExporter"
        ) as MockExporter:
            event = _ec2_event("i-term01", "terminated")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

            # Exporter should NOT be called for terminated instances
            MockExporter.return_value.get_resource.assert_not_called()

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["Properties"]["InstanceId"] == "i-term01"

    @pytest.mark.asyncio
    async def test_ec2_shutting_down_deletes_resource(
        self, processor: EC2LiveEventProcessor, mock_session: AioSession
    ) -> None:
        with patch("aws.live_events.processors.ec2.EC2InstanceExporter") as MockExporter:
            event = _ec2_event("i-shutting", "shutting-down")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)
            MockExporter.return_value.get_resource.assert_not_called()

        assert result.updated_raw_results == []
        assert result.deleted_raw_results[0]["Properties"]["InstanceId"] == "i-shutting"

    # -----------------------------------------------------------------------
    # Resilience
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_missing_instance_id_returns_empty(
        self, processor: EC2LiveEventProcessor, mock_session: AioSession
    ) -> None:
        event = make_eventbridge_event(_DETAIL_TYPE, {"state": "running"})
        result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_exporter_not_found_returns_empty(
        self, processor: EC2LiveEventProcessor, mock_session: AioSession
    ) -> None:
        with patch(
            "aws.live_events.processors.ec2.EC2InstanceExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = AsyncMock(return_value={})

            event = _ec2_event("i-notfound", "running")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_exporter_exception_returns_empty(
        self, processor: EC2LiveEventProcessor, mock_session: AioSession
    ) -> None:
        with patch(
            "aws.live_events.processors.ec2.EC2InstanceExporter"
        ) as MockExporter:
            MockExporter.return_value.get_resource = AsyncMock(
                side_effect=Exception("AWS API error")
            )

            event = _ec2_event("i-err", "running")
            result = await processor.handle(event, _ACCOUNT, _REGION, mock_session)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    # -----------------------------------------------------------------------
    # Pagination regression — multiple pages of instances
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_pagination_multiple_events_processed_independently(
        self, processor: EC2LiveEventProcessor, mock_session: AioSession
    ) -> None:
        """Each event is handled independently (pagination is in resync, not live events).

        This test verifies that processing N separate events returns N separate results
        without cross-contamination.
        """
        instance_ids = [f"i-page{n:02d}" for n in range(5)]
        results = []

        for iid in instance_ids:
            fake_resource = {
                "Type": "AWS::EC2::Instance",
                "Properties": {"InstanceId": iid, "State": {"Name": "running"}},
            }
            with patch(
                "aws.live_events.processors.ec2.EC2InstanceExporter"
            ) as MockExporter:
                MockExporter.return_value.get_resource = AsyncMock(return_value=fake_resource)
                event = _ec2_event(iid, "running")
                r = await processor.handle(event, _ACCOUNT, _REGION, mock_session)
                results.append(r)

        # Each result should contain exactly its own instance
        for i, result in enumerate(results):
            assert len(result.updated_raw_results) == 1
            assert result.updated_raw_results[0]["Properties"]["InstanceId"] == instance_ids[i]
