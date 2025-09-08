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
        expected_response: Dict[str, List[Dict[str, Any]]] = {
            "InstanceStatuses": [
                {"InstanceId": "i-1", "InstanceState": {"Name": "running"}},
                {"InstanceId": "i-2", "InstanceState": {"Name": "stopped"}},
            ]
        }
        action.client.describe_instance_status.return_value = expected_response

        result = await action.execute(identifiers)

        assert result == expected_response["InstanceStatuses"]
        action.client.describe_instance_status.assert_called_once_with(
            InstanceIds=["i-1", "i-2"], IncludeAllInstances=True
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
