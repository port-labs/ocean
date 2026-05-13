import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from aws.live_events.handlers.ec2 import EC2InstanceLiveEventHandler


def _make_ec2_event(instance_id: str, state: str) -> dict[str, Any]:
    return {
        "source": "aws.ec2",
        "detail-type": "EC2 Instance State-change Notification",
        "account": "123456789012",
        "region": "us-east-1",
        "detail": {
            "instance-id": instance_id,
            "state": state,
        },
    }


class TestEC2InstanceLiveEventHandler:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_session: AsyncMock) -> EC2InstanceLiveEventHandler:
        return EC2InstanceLiveEventHandler(mock_session)

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.ec2.EC2InstanceExporter")
    async def test_running_instance_triggers_upsert(
        self, mock_exporter_cls: MagicMock, handler: EC2InstanceLiveEventHandler
    ) -> None:
        """A running EC2 instance should be fetched and upserted into Port."""
        mock_exporter = AsyncMock()
        mock_exporter_cls.return_value = mock_exporter
        mock_exporter.get_resource.return_value = {
            "Type": "AWS::EC2::Instance",
            "Properties": {"InstanceId": "i-abc123", "State": {"Name": "running"}},
        }

        event = _make_ec2_event("i-abc123", "running")

        with patch.object(handler, "_upsert", new_callable=AsyncMock) as mock_upsert:
            await handler.handle(event, account_id="123456789012", region="us-east-1")
            mock_upsert.assert_called_once()
            args = mock_upsert.call_args[0][0]
            assert args["Properties"]["InstanceId"] == "i-abc123"

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.ec2.EC2InstanceExporter")
    async def test_terminated_instance_triggers_delete(
        self, mock_exporter_cls: MagicMock, handler: EC2InstanceLiveEventHandler
    ) -> None:
        """A terminated EC2 instance should be deleted from Port without fetching full state."""
        event = _make_ec2_event("i-dead", "terminated")

        with patch.object(handler, "_delete", new_callable=AsyncMock) as mock_delete:
            await handler.handle(event, account_id="123456789012", region="us-east-1")
            mock_delete.assert_called_once_with("i-dead")
            mock_exporter_cls.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.ec2.EC2InstanceExporter")
    async def test_shutting_down_triggers_delete(
        self, mock_exporter_cls: MagicMock, handler: EC2InstanceLiveEventHandler
    ) -> None:
        """shutting-down state is treated the same as terminated."""
        event = _make_ec2_event("i-stopping", "shutting-down")

        with patch.object(handler, "_delete", new_callable=AsyncMock) as mock_delete:
            await handler.handle(event, account_id="123456789012", region="us-east-1")
            mock_delete.assert_called_once_with("i-stopping")

    @pytest.mark.asyncio
    async def test_missing_instance_id_is_skipped(
        self, handler: EC2InstanceLiveEventHandler
    ) -> None:
        """Events without an instance-id should be silently skipped."""
        event = {
            "source": "aws.ec2",
            "detail-type": "EC2 Instance State-change Notification",
            "account": "123456789012",
            "region": "us-east-1",
            "detail": {"state": "running"},
        }

        with patch.object(handler, "_upsert", new_callable=AsyncMock) as mock_upsert:
            with patch.object(handler, "_delete", new_callable=AsyncMock) as mock_delete:
                await handler.handle(event, account_id="123456789012", region="us-east-1")
                mock_upsert.assert_not_called()
                mock_delete.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.ec2.EC2InstanceExporter")
    async def test_exporter_exception_does_not_propagate(
        self, mock_exporter_cls: MagicMock, handler: EC2InstanceLiveEventHandler
    ) -> None:
        """If the exporter raises, the handler should log and return — not crash."""
        mock_exporter = AsyncMock()
        mock_exporter_cls.return_value = mock_exporter
        mock_exporter.get_resource.side_effect = Exception("AWS API error")

        event = _make_ec2_event("i-broken", "running")

        with patch.object(handler, "_upsert", new_callable=AsyncMock) as mock_upsert:
            await handler.handle(event, account_id="123456789012", region="us-east-1")
            mock_upsert.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.ec2.EC2InstanceExporter")
    async def test_duplicate_event_idempotent(
        self, mock_exporter_cls: MagicMock, handler: EC2InstanceLiveEventHandler
    ) -> None:
        """Sending the same event twice should result in two upsert calls — Port handles idempotency."""
        mock_exporter = AsyncMock()
        mock_exporter_cls.return_value = mock_exporter
        resource = {
            "Type": "AWS::EC2::Instance",
            "Properties": {"InstanceId": "i-dup", "State": {"Name": "running"}},
        }
        mock_exporter.get_resource.return_value = resource
        event = _make_ec2_event("i-dup", "running")

        with patch.object(handler, "_upsert", new_callable=AsyncMock) as mock_upsert:
            await handler.handle(event, account_id="123456789012", region="us-east-1")
            await handler.handle(event, account_id="123456789012", region="us-east-1")
            assert mock_upsert.call_count == 2
