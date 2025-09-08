from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.ecs.cluster.actions import (
    DescribeClustersAction,
    GetClusterTagsAction,
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
                "ClusterName": "test-cluster",
                "CapacityProviders": ["FARGATE"],
                "ClusterSettings": [],
                "Configuration": None,
                "DefaultCapacityProviderStrategy": [],
                "ServiceConnectDefaults": None,
                "Tags": [],
                "Status": "ACTIVE",
                "RunningTasksCount": 5,
                "ActiveServicesCount": 2,
                "PendingTasksCount": 1,
                "RegisteredContainerInstancesCount": 3,
                "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            },
            {
                "ClusterName": "prod-cluster",
                "CapacityProviders": ["FARGATE", "FARGATE_SPOT"],
                "ClusterSettings": [],
                "Configuration": None,
                "DefaultCapacityProviderStrategy": [],
                "ServiceConnectDefaults": None,
                "Tags": [],
                "Status": "ACTIVE",
                "RunningTasksCount": 10,
                "ActiveServicesCount": 5,
                "PendingTasksCount": 0,
                "RegisteredContainerInstancesCount": 8,
                "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/prod-cluster",
            },
        ]
        assert result == expected_result
        action.client.describe_clusters.assert_called_once_with(
            clusters=cluster_arns, include=["TAGS"]
        )

    @pytest.mark.asyncio
    async def test_execute_with_missing_fields(self, action: DescribeClustersAction) -> None:
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

        expected_result = [
            {
                "ClusterName": "minimal-cluster",
                "CapacityProviders": [],
                "ClusterSettings": [],
                "Configuration": None,
                "DefaultCapacityProviderStrategy": [],
                "ServiceConnectDefaults": None,
                "Tags": [],
                "Status": None,
                "RunningTasksCount": 0,
                "ActiveServicesCount": 0,
                "PendingTasksCount": 0,
                "RegisteredContainerInstancesCount": 0,
                "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/minimal-cluster",
            }
        ]
        assert result == expected_result

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: DescribeClustersAction) -> None:
        """Test execution with empty cluster ARN list."""
        result = await action.execute([])
        assert result == []


class TestGetClusterTagsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        # Add the ECS methods and exceptions
        mock_client.list_tags_for_resource = AsyncMock()
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.ClientError = ClientError
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetClusterTagsAction:
        """Create a GetClusterTagsAction instance for testing."""
        return GetClusterTagsAction(mock_client)

    def test_inheritance(self, action: GetClusterTagsAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: GetClusterTagsAction
    ) -> None:
        """Test successful execution of get cluster tags."""
        expected_response = {
            "tags": [
                {"key": "Environment", "value": "production"},
                {"key": "Project", "value": "web-app"},
                {"key": "Owner", "value": "devops-team"},
            ]
        }
        action.client.list_tags_for_resource.return_value = expected_response

        clusters = [
            {
                "ClusterName": "tagged-cluster",
                "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/tagged-cluster",
            }
        ]

        result = await action.execute(clusters)

        assert result == [{"Tags": expected_response["tags"]}]
        action.client.list_tags_for_resource.assert_called_once_with(
            resourceArn="arn:aws:ecs:us-west-2:123456789012:cluster/tagged-cluster"
        )

        mock_logger.info.assert_called_once_with(
            "Successfully fetched cluster tagging for cluster tagged-cluster"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.actions.logger")
    async def test_execute_empty_tags(
        self, mock_logger: MagicMock, action: GetClusterTagsAction
    ) -> None:
        """Test execution when cluster has empty tags."""
        expected_response: dict[str, Any] = {"tags": []}
        action.client.list_tags_for_resource.return_value = expected_response

        clusters = [
            {
                "ClusterName": "no-tags-cluster",
                "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/no-tags-cluster",
            }
        ]

        result = await action.execute(clusters)

        assert result == [{"Tags": []}]
        action.client.list_tags_for_resource.assert_called_once_with(
            resourceArn="arn:aws:ecs:us-west-2:123456789012:cluster/no-tags-cluster"
        )

        mock_logger.info.assert_called_once_with(
            "Successfully fetched cluster tagging for cluster no-tags-cluster"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.actions.logger")
    async def test_execute_missing_tags(
        self, mock_logger: MagicMock, action: GetClusterTagsAction
    ) -> None:
        """Test execution when response doesn't contain tags."""
        expected_response: dict[str, Any] = {}  # No tags key
        action.client.list_tags_for_resource.return_value = expected_response

        clusters = [
            {
                "ClusterName": "missing-tags-cluster",
                "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/missing-tags-cluster",
            }
        ]

        result = await action.execute(clusters)

        assert result == [{"Tags": []}]
        action.client.list_tags_for_resource.assert_called_once_with(
            resourceArn="arn:aws:ecs:us-west-2:123456789012:cluster/missing-tags-cluster"
        )

    @pytest.mark.asyncio
    async def test_execute_resource_not_found_error(
        self, action: GetClusterTagsAction
    ) -> None:
        """Test execution when cluster has no tags (ResourceNotFoundException error)."""
        # Create a proper ClientError exception
        from botocore.exceptions import ClientError

        error_response = {
            "Error": {"Code": "ResourceNotFoundException", "Message": "The cluster does not exist"}
        }
        client_error = ClientError(error_response, "ListTagsForResource")  # type: ignore
        action.client.list_tags_for_resource.side_effect = client_error

        clusters = [
            {
                "ClusterName": "not-found-cluster",
                "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/not-found-cluster",
            }
        ]

        result = await action.execute(clusters)

        assert result == [{"Tags": []}]
        action.client.list_tags_for_resource.assert_called_once_with(
            resourceArn="arn:aws:ecs:us-west-2:123456789012:cluster/not-found-cluster"
        )

    @pytest.mark.asyncio
    async def test_execute_other_client_error(
        self, action: GetClusterTagsAction
    ) -> None:
        """Test execution when a different ClientError occurs."""
        # Create a proper ClientError exception for a different error
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        client_error = ClientError(error_response, "ListTagsForResource")  # type: ignore
        action.client.list_tags_for_resource.side_effect = client_error

        clusters = [
            {
                "ClusterName": "access-denied-cluster",
                "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/access-denied-cluster",
            }
        ]

        # Should catch the error and return empty tags
        result = await action.execute(clusters)
        assert result == [{"Tags": []}]
        action.client.list_tags_for_resource.assert_called_once_with(
            resourceArn="arn:aws:ecs:us-west-2:123456789012:cluster/access-denied-cluster"
        )

    @pytest.mark.asyncio
    async def test_execute_non_client_error(
        self, action: GetClusterTagsAction
    ) -> None:
        """Test execution when a non-ClientError exception occurs."""
        action.client.list_tags_for_resource.side_effect = Exception("Network error")

        clusters = [
            {
                "ClusterName": "network-error-cluster",
                "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/network-error-cluster",
            }
        ]

        # Should catch the error and return empty tags
        result = await action.execute(clusters)
        assert result == [{"Tags": []}]
        action.client.list_tags_for_resource.assert_called_once_with(
            resourceArn="arn:aws:ecs:us-west-2:123456789012:cluster/network-error-cluster"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.actions.logger")
    async def test_execute_multiple_clusters_with_mixed_results(
        self, mock_logger: MagicMock, action: GetClusterTagsAction
    ) -> None:
        """Test execution with multiple clusters where some succeed and some fail."""
        # Setup mixed responses
        action.client.list_tags_for_resource.side_effect = [
            {"tags": [{"key": "Environment", "value": "test"}]},  # Success
            Exception("Network error"),  # Failure
            {"tags": []},  # Success with empty tags
        ]

        clusters = [
            {
                "ClusterName": "cluster1",
                "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/cluster1",
            },
            {
                "ClusterName": "cluster2",
                "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/cluster2",
            },
            {
                "ClusterName": "cluster3",
                "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/cluster3",
            },
        ]

        result = await action.execute(clusters)

        # Should handle exceptions gracefully and return results for successful ones
        assert len(result) == 3
        assert result[0] == {"Tags": [{"key": "Environment", "value": "test"}]}
        assert result[1] == {"Tags": []}  # Exception handled gracefully
        assert result[2] == {"Tags": []}

        # Verify warning was logged for the failed cluster
        mock_logger.warning.assert_called_once_with(
            "Error fetching cluster tagging for cluster 'cluster2': Network error"
        )


class TestAllActionsIntegration:
    """Integration tests for all actions working together."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        # Add all ECS methods
        mock_client.list_tags_for_resource = AsyncMock()
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.ClientError = ClientError
        return mock_client

    @pytest.mark.asyncio
    async def test_all_actions_execution(self, mock_client: AsyncMock) -> None:
        """Test that all actions can be executed successfully."""
        # Setup responses for all actions
        mock_client.list_tags_for_resource.return_value = {
            "tags": [{"key": "Environment", "value": "test"}]
        }

        # Create all actions
        actions = [
            DescribeClustersAction(mock_client),
            GetClusterTagsAction(mock_client),
        ]

        # Mock cluster data
        clusters = [
            {
                "clusterName": "integration-cluster",
                "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/integration-cluster",
                "status": "ACTIVE",
                "runningTasksCount": 5,
                "activeServicesCount": 2,
                "pendingTasksCount": 1,
                "registeredContainerInstancesCount": 3,
                "capacityProviders": ["FARGATE"],
            }
        ]

        # Execute all actions
        results = []
        for action in actions:
            if isinstance(action, DescribeClustersAction):
                # Mock describe_clusters response
                mock_client.describe_clusters.return_value = {
                    "clusters": clusters
                }
                cluster_arns = ["arn:aws:ecs:us-west-2:123456789012:cluster/integration-cluster"]
                result = await action.execute(cluster_arns)
            else:  # GetClusterTagsAction
                # Convert to the format expected by GetClusterTagsAction
                cluster_for_tags = [
                    {
                        "ClusterName": "integration-cluster",
                        "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/integration-cluster",
                    }
                ]
                result = await action.execute(cluster_for_tags)
            results.append(result)

        # Verify all results
        assert len(results) == 2
        assert "ClusterName" in results[0][0]
        assert "Tags" in results[1][0]

        # Verify client methods were called
        mock_client.list_tags_for_resource.assert_called_once_with(
            resourceArn="arn:aws:ecs:us-west-2:123456789012:cluster/integration-cluster"
        )
