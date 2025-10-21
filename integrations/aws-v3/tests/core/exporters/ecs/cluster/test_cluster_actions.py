from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.ecs.cluster.actions import (
    DescribeClustersAction,
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

        # Create all actions
        actions = [
            DescribeClustersAction(mock_client),
        ]

        # Execute all actions
        results = []
        for action in actions:
            if isinstance(action, DescribeClustersAction):
                cluster_arns = [
                    "arn:aws:ecs:us-west-2:123456789012:cluster/integration-cluster"
                ]
                result = await action.execute(cluster_arns)
            results.append(result)

        # Verify all results
        assert len(results) == 1
        assert "clusterName" in results[0][0]

        # Verify client methods were called
        mock_client.describe_clusters.assert_called_once_with(
            clusters=["arn:aws:ecs:us-west-2:123456789012:cluster/integration-cluster"],
            include=["TAGS", "ATTACHMENTS", "SETTINGS", "CONFIGURATIONS", "STATISTICS"],
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

        # Execute actions and handle exceptions
        describe_result = await describe_action.execute(
            ["arn:aws:ecs:us-west-2:123456789012:cluster/mixed-cluster"]
        )

        # Verify results
        assert "clusterName" in describe_result[0]
