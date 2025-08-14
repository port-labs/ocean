from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.ecs.cluster.inspector import ECSClusterInspector
from aws.core.exporters.ecs.cluster.models import ECSCluster


class TestECSClusterInspector:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        # Add the ECS methods to avoid attribute errors
        mock_client.describe_clusters = AsyncMock()
        mock_client.list_tasks = AsyncMock()
        return mock_client

    @pytest.fixture
    def inspector(self, mock_client: AsyncMock) -> ECSClusterInspector:
        """Create an ECSClusterInspector instance for testing."""
        return ECSClusterInspector(mock_client)

    @pytest.fixture
    def cluster_arn(self) -> str:
        """Sample cluster ARN for testing."""
        return "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"

    def test_initialization(
        self, inspector: ECSClusterInspector, mock_client: AsyncMock
    ) -> None:
        """Test that the inspector initializes correctly."""
        assert inspector.client == mock_client
        assert inspector.actions_map is not None

    @pytest.mark.asyncio
    async def test_inspect_default_actions_only(
        self, inspector: ECSClusterInspector, cluster_arn: str
    ) -> None:
        """Test inspection with default actions only."""
        # Mock the action execution
        mock_action = AsyncMock()
        mock_action.execute.return_value = {
            "clusterArn": cluster_arn,
            "clusterName": "test-cluster",
            "status": "ACTIVE",
            "pendingTasksCount": 5,
        }

        with patch.object(
            inspector, "_run_action", return_value=mock_action.execute.return_value
        ):
            result = await inspector.inspect(cluster_arn, [])

        # Verify result
        assert isinstance(result, ECSCluster)
        assert result.Type == "AWS::ECS::Cluster"
        assert result.Properties.clusterArn == cluster_arn
        assert result.Properties.clusterName == "test-cluster"
        assert result.Properties.status == "ACTIVE"
        assert result.Properties.pendingTasksCount == 5

    @pytest.mark.asyncio
    async def test_inspect_with_optional_action(
        self, inspector: ECSClusterInspector, cluster_arn: str
    ) -> None:
        """Test inspection with optional action included."""
        # Mock the action executions
        mock_details_action = AsyncMock()
        mock_details_action.execute.return_value = {
            "clusterArn": cluster_arn,
            "clusterName": "test-cluster",
            "status": "ACTIVE",
        }

        mock_pending_action = AsyncMock()
        mock_pending_action.execute.return_value = {
            "pendingTaskArns": [
                "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
            ]
        }

        with patch.object(
            inspector,
            "_run_action",
            side_effect=[
                mock_details_action.execute.return_value,
                mock_pending_action.execute.return_value,
            ],
        ):
            result = await inspector.inspect(
                cluster_arn, ["GetClusterPendingTasksAction"]
            )

        # Verify result
        assert isinstance(result, ECSCluster)
        assert result.Properties.clusterArn == cluster_arn
        assert result.Properties.clusterName == "test-cluster"
        assert result.Properties.status == "ACTIVE"
        assert result.Properties.pendingTaskArns == [
            "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
        ]

    @pytest.mark.asyncio
    async def test_inspect_action_failure(
        self, inspector: ECSClusterInspector, cluster_arn: str
    ) -> None:
        """Test inspection when action fails."""
        # Mock the action execution to fail
        with patch.object(inspector, "_run_action", return_value={}):
            result = await inspector.inspect(cluster_arn, [])

        # Verify result still builds correctly
        assert isinstance(result, ECSCluster)
        assert result.Type == "AWS::ECS::Cluster"
        assert result.Properties.clusterArn == cluster_arn

    @pytest.mark.asyncio
    async def test_inspect_multiple_actions(
        self, inspector: ECSClusterInspector, cluster_arn: str
    ) -> None:
        """Test inspection with multiple actions."""
        # Mock the action executions
        mock_results = [
            {
                "clusterArn": cluster_arn,
                "clusterName": "test-cluster",
                "status": "ACTIVE",
            },
            {
                "pendingTaskArns": [
                    "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1",
                    "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-2",
                ]
            },
        ]

        with patch.object(inspector, "_run_action", side_effect=mock_results):
            result = await inspector.inspect(
                cluster_arn, ["GetClusterPendingTasksAction"]
            )

        # Verify result combines all action results
        assert isinstance(result, ECSCluster)
        assert result.Properties.clusterArn == cluster_arn
        assert result.Properties.clusterName == "test-cluster"
        assert result.Properties.status == "ACTIVE"
        assert result.Properties.pendingTaskArns == [
            "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1",
            "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-2",
        ]

    @pytest.mark.asyncio
    async def test_inspect_concurrent_execution(
        self, inspector: ECSClusterInspector, cluster_arn: str
    ) -> None:
        """Test that actions run concurrently."""
        # Mock the action executions
        mock_results = [
            {
                "clusterArn": cluster_arn,
                "clusterName": "test-cluster",
                "status": "ACTIVE",
            },
            {
                "pendingTaskArns": [
                    "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
                ]
            },
        ]

        with patch.object(
            inspector, "_run_action", side_effect=mock_results
        ) as mock_run_action:
            await inspector.inspect(cluster_arn, ["GetClusterPendingTasksAction"])

        # Verify _run_action was called for each action
        assert mock_run_action.call_count == 2

    @pytest.mark.asyncio
    async def test_inspect_builds_correct_cluster(
        self, inspector: ECSClusterInspector, cluster_arn: str
    ) -> None:
        """Test that inspector builds correct ECSCluster."""
        # Mock the action execution
        mock_data = {
            "clusterArn": cluster_arn,
            "clusterName": "test-cluster",
            "status": "ACTIVE",
            "pendingTasksCount": 5,
            "runningTasksCount": 10,
            "activeServicesCount": 2,
            "tags": [{"key": "Environment", "value": "test"}],
        }

        with patch.object(inspector, "_run_action", return_value=mock_data):
            result = await inspector.inspect(cluster_arn, [])

        # Verify the cluster is built correctly
        assert isinstance(result, ECSCluster)
        assert result.Type == "AWS::ECS::Cluster"
        assert result.Properties.clusterArn == cluster_arn
        assert result.Properties.clusterName == "test-cluster"
        assert result.Properties.status == "ACTIVE"
        assert result.Properties.pendingTasksCount == 5
        assert result.Properties.runningTasksCount == 10
        assert result.Properties.activeServicesCount == 2
        assert result.Properties.tags == [{"key": "Environment", "value": "test"}]

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.inspector.logger")
    async def test_run_action_success(
        self, mock_logger: MagicMock, inspector: ECSClusterInspector, cluster_arn: str
    ) -> None:
        """Test successful action execution."""
        # Create a mock action
        mock_action = AsyncMock()
        mock_action.__class__.__name__ = "ECSClusterDetailsAction"
        mock_action.execute.return_value = {
            "clusterArn": cluster_arn,
            "clusterName": "test-cluster",
        }

        result = await inspector._run_action(mock_action, cluster_arn)

        # Verify result
        assert result == {"clusterArn": cluster_arn, "clusterName": "test-cluster"}
        mock_action.execute.assert_called_once_with(cluster_arn)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.inspector.logger")
    async def test_run_action_failure(
        self, mock_logger: MagicMock, inspector: ECSClusterInspector, cluster_arn: str
    ) -> None:
        """Test action execution failure."""
        # Create a mock action that raises an exception
        mock_action = AsyncMock()
        mock_action.__class__.__name__ = "ECSClusterDetailsAction"
        mock_action.execute.side_effect = Exception("Test error")

        result = await inspector._run_action(mock_action, cluster_arn)

        # Verify result is empty dict and error is logged
        assert result == {}
        mock_logger.warning.assert_called_once_with(
            "ECSClusterDetailsAction failed: Test error"
        )

    @pytest.mark.asyncio
    async def test_run_action_with_different_action(
        self, inspector: ECSClusterInspector, cluster_arn: str
    ) -> None:
        """Test action execution with different action type."""
        # Create a mock action
        mock_action = AsyncMock()
        mock_action.__class__.__name__ = "GetClusterPendingTasksAction"
        mock_action.execute.return_value = {
            "pendingTaskArns": [
                "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
            ]
        }

        result = await inspector._run_action(mock_action, cluster_arn)

        # Verify result
        assert result == {
            "pendingTaskArns": [
                "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
            ]
        }
        mock_action.execute.assert_called_once_with(cluster_arn)
