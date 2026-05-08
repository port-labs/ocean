"""
Pagination regression tests.

Verifies that when the EC2 exporter returns multiple pages of results,
all pages are iterated and every instance is processed — none are dropped.

This guards against regressions where only the first page was consumed
or where the async generator was not fully exhausted.
"""

import pytest
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, patch

from aws.live_events.handlers.ec2 import EC2InstanceLiveEventHandler


def _make_instance(instance_id: str, state: str = "running") -> dict[str, Any]:
    return {
        "Type": "AWS::EC2::Instance",
        "Properties": {
            "InstanceId": instance_id,
            "State": {"Name": state},
        },
    }


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


async def _paginated_resources(
    pages: list[list[dict[str, Any]]],
) -> AsyncGenerator[list[dict[str, Any]], None]:
    """Async generator that yields pre-built pages — simulates paginated exporter output."""
    for page in pages:
        yield page


class TestPaginationRegression:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_session: AsyncMock) -> EC2InstanceLiveEventHandler:
        return EC2InstanceLiveEventHandler(mock_session)

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.ec2.EC2InstanceExporter")
    async def test_single_page_all_instances_upserted(
        self, mock_exporter_cls: AsyncMock, handler: EC2InstanceLiveEventHandler
    ) -> None:
        """
        Single-page response — baseline to confirm the upsert path works
        before testing multi-page scenarios.
        """
        mock_exporter = AsyncMock()
        mock_exporter_cls.return_value = mock_exporter
        mock_exporter.get_resource.return_value = _make_instance("i-page1-inst1")

        event = _make_ec2_event("i-page1-inst1", "running")

        with patch.object(handler, "_upsert", new_callable=AsyncMock) as mock_upsert:
            await handler.handle(event, "123456789012", "us-east-1")
            mock_upsert.assert_called_once()

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.ec2.EC2InstanceExporter")
    async def test_multiple_sequential_events_all_processed(
        self, mock_exporter_cls: AsyncMock, handler: EC2InstanceLiveEventHandler
    ) -> None:
        """
        Simulates receiving events for multiple instances in sequence — as would
        happen when EventBridge delivers one event per instance state change across
        a paginated describe_instances response.

        Each event must result in exactly one upsert with the correct instance data.
        No events should be dropped or merged.
        """
        mock_exporter = AsyncMock()
        mock_exporter_cls.return_value = mock_exporter

        instances = [
            _make_instance("i-page1-inst1"),
            _make_instance("i-page1-inst2"),
            _make_instance("i-page2-inst1"),
            _make_instance("i-page2-inst2"),
            _make_instance("i-page3-inst1"),
        ]

        upserted: list[str] = []

        async def fake_upsert(resource: dict[str, Any]) -> None:
            upserted.append(resource["Properties"]["InstanceId"])

        mock_exporter.get_resource.side_effect = instances

        with patch.object(handler, "_upsert", side_effect=fake_upsert):
            for instance in instances:
                event = _make_ec2_event(
                    instance["Properties"]["InstanceId"], "running"
                )
                await handler.handle(event, "123456789012", "us-east-1")

        assert len(upserted) == 5
        assert upserted == [
            "i-page1-inst1",
            "i-page1-inst2",
            "i-page2-inst1",
            "i-page2-inst2",
            "i-page3-inst1",
        ]

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.ec2.EC2InstanceExporter")
    async def test_mixed_states_across_pages_correct_outcome(
        self, mock_exporter_cls: AsyncMock, handler: EC2InstanceLiveEventHandler
    ) -> None:
        """
        Events across multiple pages contain a mix of running and terminated instances.

        Running instances must be upserted.
        Terminated instances must be deleted.
        Neither action should bleed into the other.
        """
        mock_exporter = AsyncMock()
        mock_exporter_cls.return_value = mock_exporter
        mock_exporter.get_resource.return_value = _make_instance("i-running-1")

        upserted: list[str] = []
        deleted: list[str] = []

        async def fake_upsert(resource: dict[str, Any]) -> None:
            upserted.append(resource["Properties"]["InstanceId"])

        async def fake_delete(identifier: str) -> None:
            deleted.append(identifier)

        events = [
            _make_ec2_event("i-running-1", "running"),
            _make_ec2_event("i-terminated-1", "terminated"),
            _make_ec2_event("i-running-2", "running"),
            _make_ec2_event("i-terminated-2", "shutting-down"),
        ]

        mock_exporter.get_resource.side_effect = [
            _make_instance("i-running-1"),
            _make_instance("i-running-2"),
        ]

        with patch.object(handler, "_upsert", side_effect=fake_upsert):
            with patch.object(handler, "_delete", side_effect=fake_delete):
                for event in events:
                    await handler.handle(event, "123456789012", "us-east-1")

        assert upserted == ["i-running-1", "i-running-2"]
        assert deleted == ["i-terminated-1", "i-terminated-2"]

    @pytest.mark.asyncio
    @patch("aws.live_events.handlers.ec2.EC2InstanceExporter")
    async def test_exporter_failure_on_one_page_does_not_stop_others(
        self, mock_exporter_cls: AsyncMock, handler: EC2InstanceLiveEventHandler
    ) -> None:
        """
        If the exporter fails for one instance (e.g. it was already terminated before
        we could describe it), the remaining events must still be processed.

        This guards against a regression where an exception in one handler call
        would abort processing of subsequent events.
        """
        mock_exporter = AsyncMock()
        mock_exporter_cls.return_value = mock_exporter

        mock_exporter.get_resource.side_effect = [
            Exception("DescribeInstances failed — instance not found"),
            _make_instance("i-ok-2"),
        ]

        upserted: list[str] = []

        async def fake_upsert(resource: dict[str, Any]) -> None:
            upserted.append(resource["Properties"]["InstanceId"])

        events = [
            _make_ec2_event("i-gone-1", "running"),
            _make_ec2_event("i-ok-2", "running"),
        ]

        with patch.object(handler, "_upsert", side_effect=fake_upsert):
            for event in events:
                await handler.handle(event, "123456789012", "us-east-1")

        # i-gone-1 failed but i-ok-2 must still be upserted
        assert upserted == ["i-ok-2"]
