from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.ecs.cluster.actions import (
    DescribeClustersAction,
    GetClusterPendingTasksAction,
)
from aws.core.interfaces.action import Action

# Type ignore for mock ECS client methods throughout this file
# mypy: disable-error-code=attr-defined


class TestDescribeClustersAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> DescribeClustersAction:
        """Create a DescribeClustersAction instance for testing."""
        return DescribeClustersAction(mock_client)

    def test_inheritance(self, action: DescribeClustersAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: DescribeClustersAction) -> None:
        """Test successful execution of describe clusters action."""
        # Mock cluster ARNs
        cluster_arns = [
            "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            "arn:aws:ecs:us-west-2:123456789012:cluster/prod-cluster",
        ]

        # Mock describe_clusters response
        action.client.describe_clusters.return_value = {
            "clusters": [
                {
                    "clusterName": "test-cluster",
                    "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
                    "status": "ACTIVE",
                    "runningTasksCount": 5,
                    "activeServicesCount": 2,
                    "pendingTasksCount": 1,
                    "registeredContainerInstancesCount": 3,
                    "capacityProviders": ["FARGATE"],
                    "tags": [],
                },
                {
                    "clusterName": "prod-cluster",
                    "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/prod-cluster",
                    "status": "ACTIVE",
                    "runningTasksCount": 10,
                    "activeServicesCount": 5,
                    "pendingTasksCount": 0,
                    "registeredContainerInstancesCount": 8,
                    "capacityProviders": ["FARGATE", "FARGATE_SPOT"],
                    "tags": [],
                },
            ]
        }

        # Execute
        result = await action.execute(cluster_arns)

        # Verify
        expected_result = [
            {
                "clusterName": "test-cluster",
                "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
                "status": "ACTIVE",
                "runningTasksCount": 5,
                "activeServicesCount": 2,
                "pendingTasksCount": 1,
                "registeredContainerInstancesCount": 3,
                "capacityProviders": ["FARGATE"],
                "tags": [],
            },
            {
                "clusterName": "prod-cluster",
                "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/prod-cluster",
                "status": "ACTIVE",
                "runningTasksCount": 10,
                "activeServicesCount": 5,
                "pendingTasksCount": 0,
                "registeredContainerInstancesCount": 8,
                "capacityProviders": ["FARGATE", "FARGATE_SPOT"],
                "tags": [],
            },
        ]
        assert result == expected_result
        action.client.describe_clusters.assert_called_once_with(
            clusters=cluster_arns,
            include=["TAGS", "ATTACHMENTS", "SETTINGS", "CONFIGURATIONS", "STATISTICS"],
        )

    @pytest.mark.asyncio
    async def test_execute_with_missing_fields(
        self, action: DescribeClustersAction
    ) -> None:
        """Test execution with clusters that have missing optional fields."""
        cluster_arns = ["arn:aws:ecs:us-west-2:123456789012:cluster/minimal-cluster"]

        # Mock describe_clusters response with minimal data
        action.client.describe_clusters.return_value = {
            "clusters": [
                {
                    "clusterName": "minimal-cluster",
                    "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/minimal-cluster",
                    # Missing optional fields
                }
            ]
        }

        result = await action.execute(cluster_arns)

        expected_result: list[dict[str, Any]] = [
            {
                "clusterName": "minimal-cluster",
                "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/minimal-cluster",
            }
        ]
        assert result == expected_result

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: DescribeClustersAction) -> None:
        """Test execution with empty cluster ARN list."""
        result = await action.execute([])
        assert result == []


class TestGetClusterPendingTasksAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        # Add the ECS methods and exceptions
        mock_client.list_tasks = AsyncMock()
        mock_client.describe_tasks = AsyncMock()
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.ClientError = ClientError
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
    async def test_execute_success(
        self, mock_logger: MagicMock, action: GetClusterPendingTasksAction
    ) -> None:
        """Test successful execution of get cluster pending tasks."""
        # Mock response
        expected_response = {
            "taskArns": [
                "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/abc123",
                "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/def456",
            ]
        }
        action.client.list_tasks.return_value = expected_response

        # Mock describe_tasks response
        describe_response = {
            "tasks": [
                {
                    "taskArn": "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/abc123",
                    "taskDefinitionArn": "arn:aws:ecs:us-west-2:123456789012:task-definition/my-app:1",
                    "family": "my-app",
                    "revision": 1,
                    "desiredStatus": "PENDING",
                    "lastStatus": "PENDING",
                },
                {
                    "taskArn": "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/def456",
                    "taskDefinitionArn": "arn:aws:ecs:us-west-2:123456789012:task-definition/my-app:1",
                    "family": "my-app",
                    "revision": 1,
                    "desiredStatus": "PENDING",
                    "lastStatus": "PENDING",
                },
            ]
        }
        action.client.describe_tasks.return_value = describe_response

        # Execute
        result = await action.execute([{"ClusterName": "test-cluster"}])

        # Verify
        expected_result = [{"PendingTasks": describe_response["tasks"]}]
        assert result == expected_result

        # Verify client was called correctly
        action.client.list_tasks.assert_called_once_with(
            cluster="test-cluster", desiredStatus="PENDING"
        )
        action.client.describe_tasks.assert_called_once_with(
            cluster="test-cluster", tasks=expected_response["taskArns"]
        )

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Successfully fetched 2 pending tasks for cluster test-cluster"
        )

    @pytest.mark.asyncio
    async def test_execute_different_cluster(
        self, action: GetClusterPendingTasksAction
    ) -> None:
        """Test execution with different cluster name."""
        expected_response = {
            "taskArns": ["arn:aws:ecs:us-west-2:123456789012:task/prod-cluster/xyz789"]
        }
        action.client.list_tasks.return_value = expected_response

        describe_response = {
            "tasks": [
                {
                    "taskArn": "arn:aws:ecs:us-west-2:123456789012:task/prod-cluster/xyz789",
                    "taskDefinitionArn": "arn:aws:ecs:us-west-2:123456789012:task-definition/prod-app:2",
                    "family": "prod-app",
                    "revision": 2,
                    "desiredStatus": "PENDING",
                    "lastStatus": "PENDING",
                }
            ]
        }
        action.client.describe_tasks.return_value = describe_response

        result = await action.execute([{"ClusterName": "prod-cluster"}])

        assert result == [{"PendingTasks": describe_response["tasks"]}]
        action.client.list_tasks.assert_called_once_with(
            cluster="prod-cluster", desiredStatus="PENDING"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.actions.logger")
    async def test_execute_no_pending_tasks(
        self, mock_logger: MagicMock, action: GetClusterPendingTasksAction
    ) -> None:
        """Test execution when cluster has no pending tasks."""
        expected_response: dict[str, Any] = {"taskArns": []}
        action.client.list_tasks.return_value = expected_response

        result = await action.execute([{"ClusterName": "empty-cluster"}])

        assert result == [{"PendingTasks": []}]
        action.client.list_tasks.assert_called_once_with(
            cluster="empty-cluster", desiredStatus="PENDING"
        )
        # describe_tasks should not be called when no tasks
        action.client.describe_tasks.assert_not_called()

        mock_logger.info.assert_called_once_with(
            "Successfully fetched 0 pending tasks for cluster empty-cluster"
        )

    @pytest.mark.asyncio
    async def test_execute_cluster_not_found_error(
        self, action: GetClusterPendingTasksAction
    ) -> None:
        """Test execution when cluster is not found (ClusterNotFoundException error)."""
        # Create a proper ClientError exception
        from botocore.exceptions import ClientError

        error_response = {
            "Error": {
                "Code": "ClusterNotFoundException",
                "Message": "Cluster not found",
            }
        }
        client_error = ClientError(error_response, "ListTasks")  # type: ignore
        action.client.list_tasks.side_effect = client_error

        result = await action.execute([{"ClusterName": "nonexistent-cluster"}])

        assert result == [{"PendingTasks": []}]
        action.client.list_tasks.assert_called_once_with(
            cluster="nonexistent-cluster", desiredStatus="PENDING"
        )

    @pytest.mark.asyncio
    async def test_execute_other_client_error(
        self, action: GetClusterPendingTasksAction
    ) -> None:
        """Test execution when a different ClientError occurs."""
        # Create a proper ClientError exception for a different error
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        client_error = ClientError(error_response, "ListTasks")  # type: ignore
        action.client.list_tasks.side_effect = client_error

        # Should not raise; returns empty tasks for errors surfaced by gather
        result = await action.execute([{"ClusterName": "access-denied-cluster"}])
        assert result == [{"PendingTasks": []}]
        action.client.list_tasks.assert_called_once_with(
            cluster="access-denied-cluster", desiredStatus="PENDING"
        )

    @pytest.mark.asyncio
    async def test_execute_non_client_error(
        self, action: GetClusterPendingTasksAction
    ) -> None:
        """Test execution when a non-ClientError exception occurs."""
        action.client.list_tasks.side_effect = Exception("Network error")

        # Should not raise; returns empty tasks on exception captured by gather
        result = await action.execute([{"ClusterName": "network-error-cluster"}])
        assert result == [{"PendingTasks": []}]
        action.client.list_tasks.assert_called_once_with(
            cluster="network-error-cluster", desiredStatus="PENDING"
        )


class TestAllActionsIntegration:
    """Integration tests for all actions working together."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        # Add all ECS methods
        mock_client.describe_clusters = AsyncMock()
        mock_client.list_tasks = AsyncMock()
        mock_client.describe_tasks = AsyncMock()
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.ClientError = ClientError
        return mock_client

    @pytest.mark.asyncio
    async def test_all_actions_execution(self, mock_client: AsyncMock) -> None:
        """Test that all actions can be executed successfully."""
        # Setup responses for all actions
        mock_client.describe_clusters.return_value = {
            "clusters": [
                {
                    "clusterName": "integration-cluster",
                    "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/integration-cluster",
                    "status": "ACTIVE",
                    "runningTasksCount": 5,
                    "activeServicesCount": 2,
                    "pendingTasksCount": 1,
                    "registeredContainerInstancesCount": 3,
                    "capacityProviders": ["FARGATE"],
                    "tags": [],
                }
            ]
        }
        mock_client.list_tasks.return_value = {
            "taskArns": [
                "arn:aws:ecs:us-west-2:123456789012:task/integration-cluster/task123"
            ]
        }
        mock_client.describe_tasks.return_value = {
            "tasks": [
                {
                    "taskArn": "arn:aws:ecs:us-west-2:123456789012:task/integration-cluster/task123",
                    "taskDefinitionArn": "arn:aws:ecs:us-west-2:123456789012:task-definition/my-app:1",
                    "family": "my-app",
                    "revision": 1,
                    "desiredStatus": "PENDING",
                    "lastStatus": "PENDING",
                }
            ]
        }

        # Create all actions
        actions = [
            DescribeClustersAction(mock_client),
            GetClusterPendingTasksAction(mock_client),
        ]

        # Execute all actions
        results = []
        for action in actions:
            if isinstance(action, DescribeClustersAction):
                cluster_arns = [
                    "arn:aws:ecs:us-west-2:123456789012:cluster/integration-cluster"
                ]
                result = await action.execute(cluster_arns)
            else:  # GetClusterPendingTasksAction
                # Convert to the format expected by GetClusterPendingTasksAction
                cluster_for_tasks = [
                    {
                        "ClusterName": "integration-cluster",
                        "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/integration-cluster",
                    }
                ]
                result = await action.execute(cluster_for_tasks)
            results.append(result)

        # Verify all results
        assert len(results) == 2
        assert "clusterName" in results[0][0]
        assert "PendingTasks" in results[1][0]

        # Verify client methods were called
        mock_client.describe_clusters.assert_called_once_with(
            clusters=["arn:aws:ecs:us-west-2:123456789012:cluster/integration-cluster"],
            include=["TAGS", "ATTACHMENTS", "SETTINGS", "CONFIGURATIONS", "STATISTICS"],
        )
        mock_client.list_tasks.assert_called_once_with(
            cluster="integration-cluster", desiredStatus="PENDING"
        )

    @pytest.mark.asyncio
    async def test_actions_with_mixed_success_failure(
        self, mock_client: AsyncMock
    ) -> None:
        """Test actions with some succeeding and some failing."""
        # Setup mixed responses - some succeed, some fail
        mock_client.describe_clusters.return_value = {
            "clusters": [
                {
                    "clusterName": "mixed-cluster",
                    "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/mixed-cluster",
                    "status": "ACTIVE",
                    "runningTasksCount": 5,
                    "activeServicesCount": 2,
                    "pendingTasksCount": 0,
                    "registeredContainerInstancesCount": 3,
                    "capacityProviders": ["FARGATE"],
                    "tags": [],
                }
            ]
        }
        mock_client.list_tasks.side_effect = Exception("Access denied")

        # Create actions
        describe_action = DescribeClustersAction(mock_client)
        pending_tasks_action = GetClusterPendingTasksAction(mock_client)

        # Execute actions and handle exceptions
        describe_result = await describe_action.execute(
            ["arn:aws:ecs:us-west-2:123456789012:cluster/mixed-cluster"]
        )

        pending_tasks_result = await pending_tasks_action.execute(
            [{"ClusterName": "mixed-cluster"}]
        )

        # Verify results
        assert "clusterName" in describe_result[0]
        assert pending_tasks_result == [
            {"PendingTasks": []}
        ]  # Exception handled gracefully
