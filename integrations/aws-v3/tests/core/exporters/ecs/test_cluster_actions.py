from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.ecs.cluster.actions import (
    ECSClusterDetailsAction,
    GetClusterPendingTasksAction,
    ECSClusterActionsMap,
)
from aws.core.interfaces.action import Action, BatchAction


# Type ignore for mock ECS client methods throughout this file
# mypy: disable-error-code=attr-defined


class TestECSClusterDetailsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        # Add the ECS methods to avoid attribute errors
        mock_client.describe_clusters = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ECSClusterDetailsAction:
        """Create a ECSClusterDetailsAction instance for testing."""
        return ECSClusterDetailsAction(mock_client)

    def test_inheritance(self, action: ECSClusterDetailsAction) -> None:
        """Test that the action inherits from BatchAction."""
        assert isinstance(action, BatchAction)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.actions.logger")
    async def test_execute_batch_success(
        self, mock_logger: MagicMock, action: ECSClusterDetailsAction
    ) -> None:
        """Test successful execution of describe_clusters in batch."""
        # Mock response
        expected_response = {
            "clusters": [
                {
                    "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
                    "clusterName": "test-cluster",
                    "status": "ACTIVE",
                    "pendingTasksCount": 5,
                    "runningTasksCount": 10,
                    "activeServicesCount": 2,
                    "tags": [{"key": "Environment", "value": "test"}],
                }
            ]
        }
        action.client.describe_clusters.return_value = expected_response

        # Execute
        cluster_arns = ["arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"]
        result = await action.execute_batch(cluster_arns)

        # Verify
        assert result == expected_response["clusters"]

        # Verify client was called correctly
        action.client.describe_clusters.assert_called_once_with(
            clusters=cluster_arns,
            include=["TAGS", "SETTINGS", "CONFIGURATIONS", "STATISTICS", "ATTACHMENTS"],
        )

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Successfully fetched ECS cluster details for 1 clusters"
        )

    @pytest.mark.asyncio
    async def test_execute_batch_empty_input(
        self, action: ECSClusterDetailsAction
    ) -> None:
        """Test execute_batch with empty input."""
        result = await action.execute_batch([])
        assert result == []
        action.client.describe_clusters.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_batch_multiple_clusters(
        self, action: ECSClusterDetailsAction
    ) -> None:
        """Test execute_batch with multiple clusters."""
        expected_response = {
            "clusters": [
                {
                    "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/cluster-1",
                    "clusterName": "cluster-1",
                    "status": "ACTIVE",
                },
                {
                    "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/cluster-2",
                    "clusterName": "cluster-2",
                    "status": "ACTIVE",
                },
            ]
        }
        action.client.describe_clusters.return_value = expected_response

        cluster_arns = [
            "arn:aws:ecs:us-west-2:123456789012:cluster/cluster-1",
            "arn:aws:ecs:us-west-2:123456789012:cluster/cluster-2",
        ]
        result = await action.execute_batch(cluster_arns)

        assert result == expected_response["clusters"]
        action.client.describe_clusters.assert_called_once_with(
            clusters=cluster_arns,
            include=["TAGS", "SETTINGS", "CONFIGURATIONS", "STATISTICS", "ATTACHMENTS"],
        )


class TestGetClusterPendingTasksAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        # Add the ECS methods to avoid attribute errors
        mock_client.list_tasks = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetClusterPendingTasksAction:
        """Create a GetClusterPendingTasksAction instance for testing."""
        return GetClusterPendingTasksAction(mock_client)

    def test_inheritance(self, action: GetClusterPendingTasksAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.actions.logger")
    async def test_execute_success_with_tasks(
        self, mock_logger: MagicMock, action: GetClusterPendingTasksAction
    ) -> None:
        """Test successful execution of list_tasks with pending tasks."""
        # Mock response
        expected_response = {
            "taskArns": [
                "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1",
                "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-2",
            ]
        }
        action.client.list_tasks.return_value = expected_response

        # Execute
        result = await action.execute(
            "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )

        # Verify
        expected_result = {"pendingTaskArns": expected_response["taskArns"]}
        assert result == expected_result

        # Verify client was called correctly
        action.client.list_tasks.assert_called_once_with(
            cluster="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            desiredStatus="PENDING",
            maxResults=100,
        )

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Found 2 pending tasks for cluster arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.actions.logger")
    async def test_execute_success_no_tasks(
        self, mock_logger: MagicMock, action: GetClusterPendingTasksAction
    ) -> None:
        """Test successful execution of list_tasks with no pending tasks."""
        # Mock response
        expected_response: dict[str, list[str]] = {"taskArns": []}
        action.client.list_tasks.return_value = expected_response

        # Execute
        result = await action.execute(
            "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )

        # Verify
        expected_result: dict[str, list[str]] = {"pendingTaskArns": []}
        assert result == expected_result

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Found 0 pending tasks for cluster arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )

    @pytest.mark.asyncio
    async def test_execute_different_cluster(
        self, action: GetClusterPendingTasksAction
    ) -> None:
        """Test execution with different cluster ARN."""
        expected_response = {
            "taskArns": ["arn:aws:ecs:us-east-1:123456789012:task/prod-cluster/task-1"]
        }
        action.client.list_tasks.return_value = expected_response

        result = await action.execute(
            "arn:aws:ecs:us-east-1:123456789012:cluster/prod-cluster"
        )

        assert result == {"pendingTaskArns": expected_response["taskArns"]}
        action.client.list_tasks.assert_called_once_with(
            cluster="arn:aws:ecs:us-east-1:123456789012:cluster/prod-cluster",
            desiredStatus="PENDING",
            maxResults=100,
        )

    @pytest.mark.asyncio
    async def test_execute_max_results_limit(
        self, action: GetClusterPendingTasksAction
    ) -> None:
        """Test that maxResults=100 is respected."""
        expected_response = {
            "taskArns": [
                f"arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-{i}"
                for i in range(100)
            ]
        }
        action.client.list_tasks.return_value = expected_response

        result = await action.execute(
            "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )

        assert len(result["pendingTaskArns"]) == 100
        action.client.list_tasks.assert_called_once_with(
            cluster="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            desiredStatus="PENDING",
            maxResults=100,
        )


class TestECSClusterActionsMap:

    def test_defaults_contains_required_actions(self) -> None:
        """Test that defaults contains the required actions."""
        actions_map = ECSClusterActionsMap()
        assert ECSClusterDetailsAction in actions_map.defaults
        assert len(actions_map.defaults) == 1

    def test_options_contains_optional_actions(self) -> None:
        """Test that options contains the optional actions."""
        actions_map = ECSClusterActionsMap()
        assert GetClusterPendingTasksAction in actions_map.options
        assert len(actions_map.options) == 1

    def test_merge_without_include(self) -> None:
        """Test merge without include returns only defaults."""
        actions_map = ECSClusterActionsMap()
        result = actions_map.merge([])
        assert len(result) == 1
        assert ECSClusterDetailsAction in result
        assert GetClusterPendingTasksAction not in result

    def test_merge_with_pending_tasks_action(self) -> None:
        """Test merge with GetClusterPendingTasksAction included."""
        actions_map = ECSClusterActionsMap()
        result = actions_map.merge(["GetClusterPendingTasksAction"])
        assert len(result) == 2
        assert ECSClusterDetailsAction in result
        assert GetClusterPendingTasksAction in result

    def test_merge_with_unknown_action(self) -> None:
        """Test merge with unknown action returns only defaults."""
        actions_map = ECSClusterActionsMap()
        result = actions_map.merge(["UnknownAction"])
        assert len(result) == 1
        assert ECSClusterDetailsAction in result
        assert GetClusterPendingTasksAction not in result

    def test_merge_with_multiple_actions(self) -> None:
        """Test merge with multiple actions."""
        actions_map = ECSClusterActionsMap()
        result = actions_map.merge(["GetClusterPendingTasksAction", "UnknownAction"])
        assert len(result) == 2
        assert ECSClusterDetailsAction in result
        assert GetClusterPendingTasksAction in result
