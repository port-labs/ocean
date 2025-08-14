import pytest

from aws.core.exporters.ecs.cluster.builder import ECSClusterBuilder
from aws.core.exporters.ecs.cluster.models import ECSCluster, ECSClusterProperties


class TestECSClusterBuilder:

    @pytest.fixture
    def cluster_arn(self) -> str:
        """Sample cluster ARN for testing."""
        return "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"

    @pytest.fixture
    def builder(self, cluster_arn: str) -> ECSClusterBuilder:
        """Create an ECSClusterBuilder instance for testing."""
        return ECSClusterBuilder(cluster_arn)

    def test_initialization(self, builder: ECSClusterBuilder, cluster_arn: str) -> None:
        """Test builder initialization with cluster ARN."""
        assert builder._cluster.Type == "AWS::ECS::Cluster"
        assert builder._cluster.Properties.clusterArn == cluster_arn

    def test_with_data_single_field(self, builder: ECSClusterBuilder) -> None:
        """Test adding single field data."""
        data = {"clusterName": "test-cluster"}

        result = builder.with_data(data)

        assert result is builder  # Returns self for chaining
        assert builder._cluster.Properties.clusterName == "test-cluster"

    def test_with_data_multiple_fields(self, builder: ECSClusterBuilder) -> None:
        """Test adding multiple field data."""
        data = {
            "clusterName": "test-cluster",
            "status": "ACTIVE",
            "pendingTasksCount": 5,
            "runningTasksCount": 10,
        }

        result = builder.with_data(data)

        assert result is builder
        assert builder._cluster.Properties.clusterName == "test-cluster"
        assert builder._cluster.Properties.status == "ACTIVE"
        assert builder._cluster.Properties.pendingTasksCount == 5
        assert builder._cluster.Properties.runningTasksCount == 10

    def test_with_data_unknown_field(self, builder: ECSClusterBuilder) -> None:
        """Test adding unknown field (should raise ValueError due to extra='forbid')."""
        data = {"clusterName": "test-cluster", "unknownField": "unknown-value"}

        # Should raise ValueError since ECSClusterProperties has extra='forbid'
        with pytest.raises(ValueError, match="object has no field"):
            builder.with_data(data)

    def test_with_data_overwrite_field(self, builder: ECSClusterBuilder) -> None:
        """Test overwriting existing field."""
        # Set initial value
        builder.with_data({"clusterName": "initial-name"})

        # Overwrite with new value
        result = builder.with_data({"clusterName": "updated-name"})

        assert result is builder
        assert builder._cluster.Properties.clusterName == "updated-name"

    def test_with_data_pending_task_arns(self, builder: ECSClusterBuilder) -> None:
        """Test adding pending task ARNs data."""
        task_arns = [
            "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1",
            "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-2",
        ]
        data = {"pendingTaskArns": task_arns}

        result = builder.with_data(data)

        assert result is builder
        assert builder._cluster.Properties.pendingTaskArns == task_arns

    def test_with_data_complex_fields(self, builder: ECSClusterBuilder) -> None:
        """Test adding complex field data."""
        data = {
            "tags": [{"key": "Environment", "value": "test"}],
            "settings": [{"name": "containerInsights", "value": "enabled"}],
            "capacityProviders": ["FARGATE", "FARGATE_SPOT"],
        }

        result = builder.with_data(data)

        assert result is builder
        assert builder._cluster.Properties.tags == [
            {"key": "Environment", "value": "test"}
        ]
        assert builder._cluster.Properties.settings == [
            {"name": "containerInsights", "value": "enabled"}
        ]
        assert builder._cluster.Properties.capacityProviders == [
            "FARGATE",
            "FARGATE_SPOT",
        ]

    def test_build_returns_ecs_cluster(self, builder: ECSClusterBuilder) -> None:
        """Test build returns correct ECSCluster object."""
        result = builder.build()

        assert isinstance(result, ECSCluster)
        assert result.Type == "AWS::ECS::Cluster"
        assert isinstance(result.Properties, ECSClusterProperties)

    def test_build_preserves_all_data(self, builder: ECSClusterBuilder) -> None:
        """Test build preserves all added data."""
        data = {
            "clusterName": "test-cluster",
            "status": "ACTIVE",
            "pendingTasksCount": 5,
            "runningTasksCount": 10,
            "activeServicesCount": 2,
            "tags": [{"key": "Environment", "value": "test"}],
            "pendingTaskArns": [
                "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
            ],
        }

        builder.with_data(data)
        result = builder.build()

        assert result.Properties.clusterName == "test-cluster"
        assert result.Properties.status == "ACTIVE"
        assert result.Properties.pendingTasksCount == 5
        assert result.Properties.runningTasksCount == 10
        assert result.Properties.activeServicesCount == 2
        assert result.Properties.tags == [{"key": "Environment", "value": "test"}]
        assert result.Properties.pendingTaskArns == [
            "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
        ]

    def test_build_returns_same_object(self, builder: ECSClusterBuilder) -> None:
        """Test build returns the same object instance."""
        cluster1 = builder.build()
        cluster2 = builder.build()

        assert cluster1 is cluster2  # Same object instance

    def test_chaining(self, builder: ECSClusterBuilder) -> None:
        """Test method chaining works correctly."""
        result = (
            builder.with_data({"clusterName": "test-cluster"})
            .with_data({"status": "ACTIVE"})
            .with_data({"pendingTasksCount": 5})
            .build()
        )

        assert result.Properties.clusterName == "test-cluster"
        assert result.Properties.status == "ACTIVE"
        assert result.Properties.pendingTasksCount == 5

    def test_empty_data(self, builder: ECSClusterBuilder) -> None:
        """Test with empty data dictionary."""
        result = builder.with_data({})

        assert result is builder
        # Should not cause any errors

    def test_none_values(self, builder: ECSClusterBuilder) -> None:
        """Test with None values in data."""
        data = {"clusterName": None, "status": None, "pendingTasksCount": None}

        result = builder.with_data(data)

        assert result is builder
        assert builder._cluster.Properties.clusterName is None
        assert builder._cluster.Properties.status is None
        assert builder._cluster.Properties.pendingTasksCount is None
