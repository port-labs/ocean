import pytest
from typing import Any
from unittest.mock import AsyncMock
from botocore.exceptions import ClientError
from aws.core.exporters.eks.cluster.actions import DescribeClusterAction
from aws.core.interfaces.action import Action


class TestDescribeClusterAction:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        # Add the EKS methods to avoid attribute errors
        mock_client.describe_cluster = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> DescribeClusterAction:
        """Create a DescribeClusterAction instance for testing."""
        return DescribeClusterAction(mock_client)

    def test_inheritance(self, action: DescribeClusterAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: DescribeClusterAction) -> None:
        """Test successful execution of describe cluster action."""
        cluster_names = ["test-cluster"]

        # Mock EKS describe_cluster response
        action.client.describe_cluster.return_value = {
            "cluster": {
                "name": "test-cluster",
                "arn": "arn:aws:eks:us-west-2:123456789012:cluster/test-cluster",
                "version": "1.28",
                "status": "ACTIVE",
                "endpoint": "https://ABC123DEF4567890.gr7.us-west-2.eks.amazonaws.com",
                "roleArn": "arn:aws:iam::123456789012:role/EKSClusterRole",
                "resourcesVpcConfig": {
                    "subnetIds": ["subnet-12345", "subnet-67890"],
                    "securityGroupIds": ["sg-12345"],
                    "endpointPrivateAccess": True,
                    "endpointPublicAccess": True,
                    "publicAccessCidrs": ["0.0.0.0/0"],
                },
                "logging": {
                    "clusterLogging": [
                        {"enabled": True, "types": ["api", "audit", "authenticator"]}
                    ]
                },
                "platformVersion": "eks.5",
                "createdAt": 1640995200,
                "tags": {"Environment": "test", "Project": "eks-test"},
            }
        }

        result = await action.execute(cluster_names)

        expected_result = [
            {
                "name": "test-cluster",
                "arn": "arn:aws:eks:us-west-2:123456789012:cluster/test-cluster",
                "version": "1.28",
                "status": "ACTIVE",
                "endpoint": "https://ABC123DEF4567890.gr7.us-west-2.eks.amazonaws.com",
                "roleArn": "arn:aws:iam::123456789012:role/EKSClusterRole",
                "resourcesVpcConfig": {
                    "subnetIds": ["subnet-12345", "subnet-67890"],
                    "securityGroupIds": ["sg-12345"],
                    "endpointPrivateAccess": True,
                    "endpointPublicAccess": True,
                    "publicAccessCidrs": ["0.0.0.0/0"],
                },
                "logging": {
                    "clusterLogging": [
                        {"enabled": True, "types": ["api", "audit", "authenticator"]}
                    ]
                },
                "platformVersion": "eks.5",
                "createdAt": 1640995200,
                "tags": {"Environment": "test", "Project": "eks-test"},
            }
        ]

        assert result == expected_result
        action.client.describe_cluster.assert_called_once_with(name="test-cluster")

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: DescribeClusterAction) -> None:
        """Test execution with empty cluster name list."""
        result = await action.execute([])
        assert result == []
        action.client.describe_cluster.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_multiple_clusters_concurrent(
        self, action: DescribeClusterAction
    ) -> None:
        """Test that when multiple cluster names are provided, all are fetched concurrently."""
        cluster_names = ["cluster1", "cluster2", "cluster3"]

        # Mock different responses for each cluster
        def mock_describe_cluster(name: str) -> dict[str, Any]:
            return {
                "cluster": {
                    "name": name,
                    "arn": f"arn:aws:eks:us-west-2:123456789012:cluster/{name}",
                    "version": "1.28",
                    "status": "ACTIVE",
                }
            }

        action.client.describe_cluster.side_effect = mock_describe_cluster

        result = await action.execute(cluster_names)

        assert len(result) == 3
        assert result[0]["name"] == "cluster1"
        assert result[1]["name"] == "cluster2"
        assert result[2]["name"] == "cluster3"

        # Verify all clusters were called
        assert action.client.describe_cluster.call_count == 3
        action.client.describe_cluster.assert_any_call(name="cluster1")
        action.client.describe_cluster.assert_any_call(name="cluster2")
        action.client.describe_cluster.assert_any_call(name="cluster3")

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: DescribeClusterAction
    ) -> None:
        """Test concurrent execution with recoverable exceptions (ResourceNotFound, AccessDenied)."""
        cluster_names = ["cluster1", "cluster2", "cluster3"]

        # Mock responses - cluster2 will have a recoverable exception
        def mock_describe_cluster(name: str) -> dict[str, Any]:
            if name == "cluster2":
                # Create a ResourceNotFoundException (recoverable)
                error_response = {
                    "Error": {
                        "Code": "ResourceNotFoundException",
                        "Message": f"No cluster found for name: {name}",
                    }
                }
                raise ClientError(error_response, "describe_cluster")  # type: ignore
            return {
                "cluster": {
                    "name": name,
                    "arn": f"arn:aws:eks:us-west-2:123456789012:cluster/{name}",
                    "version": "1.28",
                    "status": "ACTIVE",
                }
            }

        action.client.describe_cluster.side_effect = mock_describe_cluster

        result = await action.execute(cluster_names)

        # Should return only successful clusters (cluster1 and cluster3)
        # cluster2 should be skipped due to recoverable exception
        assert len(result) == 2
        assert result[0]["name"] == "cluster1"
        assert result[1]["name"] == "cluster3"

        # Verify all clusters were called
        assert action.client.describe_cluster.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: DescribeClusterAction
    ) -> None:
        """Test that non-recoverable exceptions break the action."""
        cluster_names = ["cluster1", "cluster2"]

        # Mock responses - cluster2 will have a non-recoverable exception
        def mock_describe_cluster(name: str) -> dict[str, Any]:
            if name == "cluster2":
                # Create a non-recoverable exception (network error, etc.)
                raise Exception("Network timeout")
            return {
                "cluster": {
                    "name": name,
                    "arn": f"arn:aws:eks:us-west-2:123456789012:cluster/{name}",
                    "version": "1.28",
                    "status": "ACTIVE",
                }
            }

        action.client.describe_cluster.side_effect = mock_describe_cluster

        # Should raise the non-recoverable exception
        with pytest.raises(Exception, match="Network timeout"):
            await action.execute(cluster_names)
