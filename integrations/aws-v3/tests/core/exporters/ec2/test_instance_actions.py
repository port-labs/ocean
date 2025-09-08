from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock
import pytest

from aws.core.exporters.ec2.instance.actions import (
    GetInstanceStatusAction,
    DescribeInstancesAction,
    EC2InstanceActionsMap,
)
from aws.core.interfaces.action import Action


class TestGetInstanceStatusAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.describe_instance_status = AsyncMock()
        return client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetInstanceStatusAction:
        return GetInstanceStatusAction(mock_client)

    def test_inheritance(self, action: GetInstanceStatusAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(
        self, mock_logger: MagicMock, action: GetInstanceStatusAction
    ) -> None:
        identifiers = [
            {"InstanceId": "i-1"},
            {"InstanceId": "i-2"},
        ]

        # Mock should return different responses for each individual call
        def mock_describe_instance_status(
            InstanceIds: List[str], **kwargs
        ) -> Dict[str, Any]:
            if InstanceIds == ["i-1"]:
                return {
                    "InstanceStatuses": [
                        {"InstanceId": "i-1", "InstanceState": {"Name": "running"}}
                    ]
                }
            elif InstanceIds == ["i-2"]:
                return {
                    "InstanceStatuses": [
                        {"InstanceId": "i-2", "InstanceState": {"Name": "stopped"}}
                    ]
                }
            else:
                return {"InstanceStatuses": []}

        action.client.describe_instance_status.side_effect = (
            mock_describe_instance_status
        )

        result = await action.execute(identifiers)

        expected_result = [
            {"InstanceId": "i-1", "InstanceState": {"Name": "running"}},
            {"InstanceId": "i-2", "InstanceState": {"Name": "stopped"}},
        ]
        assert result == expected_result

        # Verify that describe_instance_status was called twice (once for each instance)
        assert action.client.describe_instance_status.call_count == 2
        action.client.describe_instance_status.assert_any_call(
            InstanceIds=["i-1"], IncludeAllInstances=True
        )
        action.client.describe_instance_status.assert_any_call(
            InstanceIds=["i-2"], IncludeAllInstances=True
        )


class TestDescribeInstancesAction:

    @pytest.fixture
    def action(self) -> DescribeInstancesAction:
        return DescribeInstancesAction(AsyncMock())

    def test_inheritance(self, action: DescribeInstancesAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_returns_input(self, action: DescribeInstancesAction) -> None:
        instances = [{"InstanceId": "i-1"}, {"InstanceId": "i-2"}]
        assert await action.execute(instances) == instances


class TestEC2InstanceActionsMap:

    @pytest.mark.asyncio
    async def test_merge_includes_defaults(self, mock_logger: MagicMock) -> None:
        action_map = EC2InstanceActionsMap()
        merged = action_map.merge([])

        # Defaults are DescribeInstancesAction and GetInstanceStatusAction
        names = [cls.__name__ for cls in merged]
        assert "DescribeInstancesAction" in names
        assert "GetInstanceStatusAction" in names

    @pytest.mark.asyncio
    async def test_merge_with_options(self, mock_logger: MagicMock) -> None:
        class DummyAction(Action):
            async def _execute(self, identifiers: List[Any]) -> List[Dict[str, Any]]:
                return [{"dummy": True}]

        EC2InstanceActionsMap.options = [DummyAction]
        try:
            action_map = EC2InstanceActionsMap()
            merged = action_map.merge(["DummyAction"])  # Include our dummy

            names = [cls.__name__ for cls in merged]
            assert "DescribeInstancesAction" in names
            assert "GetInstanceStatusAction" in names
            assert "DummyAction" in names
        finally:
            EC2InstanceActionsMap.options = []  # reset to not influence other tests
