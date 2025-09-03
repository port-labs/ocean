from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.ec2.instances.actions import (
    GetInstanceStatusAction,
    EC2InstanceActionsMap,
)
from aws.core.interfaces.action import Action

# Type ignore for mock EC2 client methods throughout this file
# mypy: disable-error-code=attr-defined


class TestGetInstanceStatusAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        mock_client.describe_instance_status = AsyncMock()
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.ClientError = ClientError
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetInstanceStatusAction:
        """Create a GetInstanceStatusAction instance for testing."""
        return GetInstanceStatusAction(mock_client)

    def test_inheritance(self, action: GetInstanceStatusAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instances.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: GetInstanceStatusAction
    ) -> None:
        """Test successful status retrieval."""
        expected_response = {
            "InstanceStatuses": [
                {
                    "InstanceId": "i-1234567890abcdef0",
                    "InstanceStatus": {"Status": "ok", "Details": []},
                    "SystemStatus": {"Status": "ok", "Details": []},
                    "Events": [],
                }
            ]
        }
        action.client.describe_instance_status.return_value = expected_response

        result = await action.execute("i-1234567890abcdef0")

        assert "InstanceStatus" in result
        assert "SystemStatus" in result
        assert "Events" in result
        assert result["InstanceStatus"]["Status"] == "ok"
        assert result["SystemStatus"]["Status"] == "ok"

        action.client.describe_instance_status.assert_called_once_with(
            InstanceIds=["i-1234567890abcdef0"], IncludeAllInstances=True
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instances.actions.logger")
    async def test_execute_no_status(
        self, mock_logger: MagicMock, action: GetInstanceStatusAction
    ) -> None:
        """Test execution when no status information is available."""
        expected_response: dict[str, Any] = {"InstanceStatuses": []}
        action.client.describe_instance_status.return_value = expected_response

        result = await action.execute("i-1234567890abcdef0")

        assert result == {}
        mock_logger.info.assert_called_once_with(
            "No status information found for instance i-1234567890abcdef0"
        )

    @pytest.mark.asyncio
    async def test_execute_client_error(self, action: GetInstanceStatusAction) -> None:
        """Test execution when a ClientError occurs."""
        error_response = {
            "Error": {
                "Code": "InvalidInstanceID.NotFound",
                "Message": "Instance not found",
            }
        }
        client_error = ClientError(error_response, "DescribeInstanceStatus")  # type: ignore
        action.client.describe_instance_status.side_effect = client_error

        # The exception should propagate up since it's not handled in the action
        with pytest.raises(ClientError, match="Instance not found"):
            await action.execute("i-1234567890abcdef0")


class TestEC2InstanceActionsMap:
    """Test the EC2InstanceActionsMap class."""

    def test_defaults_list(self) -> None:
        """Test that defaults list contains expected actions."""
        actions_map = EC2InstanceActionsMap()

        assert len(actions_map.defaults) == 0

    def test_options_list(self) -> None:
        """Test that options list contains expected actions."""
        actions_map = EC2InstanceActionsMap()

        assert GetInstanceStatusAction in actions_map.options
        assert len(actions_map.options) == 1

    def test_merge_with_empty_include(self) -> None:
        """Test merge with empty include list."""
        actions_map = EC2InstanceActionsMap()
        result = actions_map.merge([])

        # Should only include defaults
        assert len(result) == 0

    def test_merge_with_include(self) -> None:
        """Test merge with include list."""
        actions_map = EC2InstanceActionsMap()
        result = actions_map.merge(["GetInstanceStatusAction"])

        # Should include specified options
        assert len(result) == 1
        assert GetInstanceStatusAction in result

    def test_merge_with_nonexistent_action(self) -> None:
        """Test merge with non-existent action name."""
        actions_map = EC2InstanceActionsMap()
        result = actions_map.merge(["NonExistentAction"])

        # Should only include defaults, ignore non-existent
        assert len(result) == 0
