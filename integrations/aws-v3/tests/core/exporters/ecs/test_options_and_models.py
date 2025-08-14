import pytest
from pydantic import ValidationError

from aws.core.exporters.ecs.cluster.options import (
    SingleECSClusterExporterOptions,
    PaginatedECSClusterExporterOptions,
)
from aws.core.exporters.ecs.cluster.models import (
    ECSCluster,
    ECSClusterProperties,
)


class TestECSClusterOptions:

    def test_single_options_validation(self) -> None:
        """Test SingleECSClusterExporterOptions validation."""
        # Valid options
        options = SingleECSClusterExporterOptions(
            region="us-west-2",
            cluster_arn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            include=["GetClusterPendingTasksAction"],
        )

        assert options.region == "us-west-2"
        assert (
            options.cluster_arn
            == "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )
        assert options.include == ["GetClusterPendingTasksAction"]

    def test_single_options_validation_missing_cluster_arn(self) -> None:
        """Test SingleECSClusterExporterOptions validation with missing cluster_arn."""
        with pytest.raises(ValidationError):
            SingleECSClusterExporterOptions(  # type: ignore[call-arg]
                region="us-west-2",
                # Missing cluster_arn
                include=[],
            )

    def test_single_options_validation_empty_include(self) -> None:
        """Test SingleECSClusterExporterOptions validation with empty include."""
        options = SingleECSClusterExporterOptions(
            region="us-west-2",
            cluster_arn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            include=[],
        )

        assert options.include == []

    def test_paginated_options_validation(self) -> None:
        """Test PaginatedECSClusterExporterOptions validation."""
        # Valid options
        options = PaginatedECSClusterExporterOptions(
            region="us-west-2", include=["GetClusterPendingTasksAction"]
        )

        assert options.region == "us-west-2"
        assert options.include == ["GetClusterPendingTasksAction"]

    def test_paginated_options_validation_empty_include(self) -> None:
        """Test PaginatedECSClusterExporterOptions validation with empty include."""
        options = PaginatedECSClusterExporterOptions(region="us-west-2", include=[])

        assert options.include == []

    def test_options_inheritance(self) -> None:
        """Test options inherit from ExporterOptions."""
        single_options = SingleECSClusterExporterOptions(
            region="us-west-2",
            cluster_arn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
        )

        paginated_options = PaginatedECSClusterExporterOptions(region="us-west-2")

        # Both should have region and include fields
        assert hasattr(single_options, "region")
        assert hasattr(single_options, "include")
        assert hasattr(paginated_options, "region")
        assert hasattr(paginated_options, "include")


class TestECSClusterModels:

    def test_ecs_cluster_properties_validation(self) -> None:
        """Test ECSClusterProperties validation."""
        # Valid properties
        properties = ECSClusterProperties(
            clusterArn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            clusterName="test-cluster",
            status="ACTIVE",
            pendingTasksCount=5,
            runningTasksCount=10,
            activeServicesCount=2,
        )

        assert (
            properties.clusterArn
            == "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )
        assert properties.clusterName == "test-cluster"
        assert properties.status == "ACTIVE"
        assert properties.pendingTasksCount == 5
        assert properties.runningTasksCount == 10
        assert properties.activeServicesCount == 2

    def test_ecs_cluster_properties_validation_with_complex_fields(self) -> None:
        """Test ECSClusterProperties validation with complex fields."""
        properties = ECSClusterProperties(
            clusterArn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            clusterName="test-cluster",
            tags=[{"key": "Environment", "value": "test"}],
            settings=[{"name": "containerInsights", "value": "enabled"}],
            capacityProviders=["FARGATE", "FARGATE_SPOT"],
            pendingTaskArns=[
                "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
            ],
        )

        assert properties.tags == [{"key": "Environment", "value": "test"}]
        assert properties.settings == [
            {"name": "containerInsights", "value": "enabled"}
        ]
        assert properties.capacityProviders == ["FARGATE", "FARGATE_SPOT"]
        assert properties.pendingTaskArns == [
            "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
        ]

    def test_ecs_cluster_properties_validation_extra_forbid(self) -> None:
        """Test ECSClusterProperties extra='forbid' behavior."""
        # Should not allow extra fields
        with pytest.raises(ValidationError):
            ECSClusterProperties(  # type: ignore[call-arg]
                clusterArn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
                clusterName="test-cluster",
                unknownField="unknown-value",  # This should cause validation error
            )

    def test_ecs_cluster_validation(self) -> None:
        """Test ECSCluster validation."""
        # Valid cluster
        cluster = ECSCluster(
            Properties=ECSClusterProperties(
                clusterArn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
                clusterName="test-cluster",
                status="ACTIVE",
            )
        )

        assert cluster.Type == "AWS::ECS::Cluster"
        assert (
            cluster.Properties.clusterArn
            == "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )
        assert cluster.Properties.clusterName == "test-cluster"
        assert cluster.Properties.status == "ACTIVE"

    def test_ecs_cluster_defaults(self) -> None:
        """Test ECSCluster default values."""
        cluster = ECSCluster()

        assert cluster.Type == "AWS::ECS::Cluster"
        assert cluster.Properties is not None
        assert isinstance(cluster.Properties, ECSClusterProperties)

    def test_ecs_cluster_extra_fields(self) -> None:
        """Test ECSCluster extra field handling."""
        # Should allow extra fields due to extra='ignore'
        cluster = ECSCluster(  # type: ignore[call-arg]
            Properties=ECSClusterProperties(
                clusterArn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
            ),
            extraField="extra-value",  # This should be ignored
        )

        assert cluster.Type == "AWS::ECS::Cluster"
        assert (
            cluster.Properties.clusterArn
            == "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )

    def test_ecs_cluster_properties_all_fields(self) -> None:
        """Test ECSClusterProperties with all possible fields."""
        properties = ECSClusterProperties(
            clusterArn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            clusterName="test-cluster",
            status="ACTIVE",
            activeServicesCount=2,
            pendingTasksCount=5,
            runningTasksCount=10,
            registeredContainerInstancesCount=3,
            capacityProviders=["FARGATE"],
            defaultCapacityProviderStrategy=[
                {"capacityProvider": "FARGATE", "weight": 1}
            ],
            settings=[{"name": "containerInsights", "value": "enabled"}],
            configuration={"executeCommandConfiguration": {"logging": "DEFAULT"}},
            statistics=[{"name": "cpuUtilization", "value": "75.5"}],
            tags=[{"key": "Environment", "value": "test"}],
            attachments=[{"id": "attachment-1", "type": "capacity-provider"}],
            attachmentsStatus="ACTIVE",
            serviceConnectDefaults={"namespace": "test-namespace"},
            pendingTaskArns=[
                "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
            ],
        )

        # Verify all fields are set correctly
        assert (
            properties.clusterArn
            == "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )
        assert properties.clusterName == "test-cluster"
        assert properties.status == "ACTIVE"
        assert properties.activeServicesCount == 2
        assert properties.pendingTasksCount == 5
        assert properties.runningTasksCount == 10
        assert properties.registeredContainerInstancesCount == 3
        assert properties.capacityProviders == ["FARGATE"]
        assert properties.defaultCapacityProviderStrategy == [
            {"capacityProvider": "FARGATE", "weight": 1}
        ]
        assert properties.settings == [
            {"name": "containerInsights", "value": "enabled"}
        ]
        assert properties.configuration == {
            "executeCommandConfiguration": {"logging": "DEFAULT"}
        }
        assert properties.statistics == [{"name": "cpuUtilization", "value": "75.5"}]
        assert properties.tags == [{"key": "Environment", "value": "test"}]
        assert properties.attachments == [
            {"id": "attachment-1", "type": "capacity-provider"}
        ]
        assert properties.attachmentsStatus == "ACTIVE"
        assert properties.serviceConnectDefaults == {"namespace": "test-namespace"}
        assert properties.pendingTaskArns == [
            "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
        ]

    def test_ecs_cluster_properties_none_values(self) -> None:
        """Test ECSClusterProperties with None values."""
        properties = ECSClusterProperties(
            clusterArn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            clusterName=None,
            status=None,
            pendingTasksCount=None,
        )

        assert (
            properties.clusterArn
            == "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )
        assert properties.clusterName is None
        assert properties.status is None
        assert properties.pendingTasksCount is None

    def test_ecs_cluster_dict_method(self) -> None:
        """Test ECSCluster dict() method."""
        cluster = ECSCluster(
            Properties=ECSClusterProperties(
                clusterArn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
                clusterName="test-cluster",
                status="ACTIVE",
            )
        )

        cluster_dict = cluster.dict()

        assert cluster_dict["Type"] == "AWS::ECS::Cluster"
        assert (
            cluster_dict["Properties"]["clusterArn"]
            == "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )
        assert cluster_dict["Properties"]["clusterName"] == "test-cluster"
        assert cluster_dict["Properties"]["status"] == "ACTIVE"

    def test_ecs_cluster_dict_exclude_none(self) -> None:
        """Test ECSCluster dict() method with exclude_none=True."""
        cluster = ECSCluster(
            Properties=ECSClusterProperties(
                clusterArn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
                clusterName=None,  # None value
                status="ACTIVE",
            )
        )

        cluster_dict = cluster.dict(exclude_none=True)

        assert cluster_dict["Type"] == "AWS::ECS::Cluster"
        assert (
            cluster_dict["Properties"]["clusterArn"]
            == "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )
        assert cluster_dict["Properties"]["status"] == "ACTIVE"
        assert "clusterName" not in cluster_dict["Properties"]  # None value excluded
