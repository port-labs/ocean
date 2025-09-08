from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.ecs.cluster.exporter import EcsClusterExporter
from aws.core.exporters.ecs.cluster.models import (
    SingleClusterRequest,
    PaginatedClusterRequest,
    Cluster,
    ClusterProperties,
)


class TestEcsClusterExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AioSession for testing."""
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> EcsClusterExporter:
        """Create an EcsClusterExporter instance for testing."""
        return EcsClusterExporter(mock_session)

    def test_service_name(self, exporter: EcsClusterExporter) -> None:
        """Test that the service name is correctly set."""
        assert exporter._service_name == "ecs"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        """Test that the exporter initializes correctly."""
        exporter = EcsClusterExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.cluster.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EcsClusterExporter,
    ) -> None:
        """Test successful single resource retrieval."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Create expected Cluster response
        expected_cluster = Cluster(
            Properties=ClusterProperties(
                ClusterName="test-cluster",
                Status="ACTIVE",
                RunningTasksCount=5,
                ActiveServicesCount=2,
                PendingTasksCount=1,
                RegisteredContainerInstancesCount=3,
                CapacityProviders=["FARGATE"],
                Arn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
                Tags=[{"key": "Environment", "value": "test"}],
            ),
        )
        mock_inspector.inspect.return_value = [expected_cluster.dict(exclude_none=True)]

        # Create options
        options = SingleClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            cluster_name="test-cluster",
            include=[],
        )

        # Execute
        result = await exporter.get_resource(options)

        # Verify
        assert result == expected_cluster.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "ecs")
        # ResourceInspector was called correctly
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once_with(
            [{"clusterName": "test-cluster"}], []
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.cluster.exporter.ResourceInspector")
    async def test_get_resource_with_different_options(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EcsClusterExporter,
    ) -> None:
        """Test single resource retrieval with different configuration options."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        expected_cluster = Cluster(
            Properties=ClusterProperties(
                ClusterName="prod-cluster",
                Status="ACTIVE",
                RunningTasksCount=10,
                ActiveServicesCount=5,
                PendingTasksCount=0,
                RegisteredContainerInstancesCount=8,
                CapacityProviders=["FARGATE", "FARGATE_SPOT"],
                Arn="arn:aws:ecs:us-west-2:123456789012:cluster/prod-cluster",
            ),
        )
        mock_inspector.inspect.return_value = [expected_cluster.dict(exclude_none=True)]

        # Create options with no includes
        options = SingleClusterRequest(
            region="eu-west-1",
            account_id="123456789012",
            cluster_name="prod-cluster",
            include=[],
        )

        # Execute
        result = await exporter.get_resource(options)

        # Verify
        assert result == expected_cluster.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "eu-west-1", "ecs")
        # ResourceInspector was called correctly
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once_with(
            [{"clusterName": "prod-cluster"}], []
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.exporter.AioBaseClientProxy")
    async def test_get_paginated_resources_success(
        self,
        mock_proxy_class: MagicMock,
        exporter: EcsClusterExporter,
    ) -> None:
        """Test successful paginated resource retrieval."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock paginator - return the async generator directly
        async def mock_paginate() -> AsyncGenerator[list[str], None]:
            yield [
                "arn:aws:ecs:us-west-2:123456789012:cluster/cluster1",
                "arn:aws:ecs:us-west-2:123456789012:cluster/cluster2",
            ]
            yield ["arn:aws:ecs:us-west-2:123456789012:cluster/cluster3"]

        # Create an object that has a paginate method returning the async generator
        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[str], None]:
                return mock_paginate()

        # Make sure get_paginator returns our MockPaginator, not a coroutine
        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Mock describe_clusters response for each page
        def mock_describe_clusters(
            clusters: list[str], include: list[str] | None = None
        ) -> dict[str, Any]:
            if "cluster1" in clusters[0] and "cluster2" in clusters[1]:
                # First page - clusters 1 and 2
                return {
                    "clusters": [
                        {
                            "clusterName": "cluster1",
                            "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/cluster1",
                            "status": "ACTIVE",
                            "runningTasksCount": 5,
                            "activeServicesCount": 2,
                            "pendingTasksCount": 1,
                            "registeredContainerInstancesCount": 3,
                            "capacityProviders": ["FARGATE"],
                            "tags": [{"key": "Environment", "value": "test"}],
                        },
                        {
                            "clusterName": "cluster2",
                            "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/cluster2",
                            "status": "ACTIVE",
                            "runningTasksCount": 8,
                            "activeServicesCount": 3,
                            "pendingTasksCount": 0,
                            "registeredContainerInstancesCount": 5,
                            "capacityProviders": ["FARGATE", "FARGATE_SPOT"],
                            "tags": [{"key": "Environment", "value": "prod"}],
                        },
                    ]
                }
            else:
                # Second page - cluster 3
                return {
                    "clusters": [
                        {
                            "clusterName": "cluster3",
                            "clusterArn": "arn:aws:ecs:us-west-2:123456789012:cluster/cluster3",
                            "status": "ACTIVE",
                            "runningTasksCount": 3,
                            "activeServicesCount": 1,
                            "pendingTasksCount": 2,
                            "registeredContainerInstancesCount": 2,
                            "capacityProviders": ["FARGATE"],
                            "tags": [{"key": "Environment", "value": "dev"}],
                        },
                    ]
                }

        mock_client.describe_clusters.side_effect = mock_describe_clusters

        # Tags are now included automatically with describe_clusters

        # Create options
        options = PaginatedClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            include=[],
        )

        # Execute and collect results
        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        # Verify
        assert len(results) == 3
        # Check that we got cluster data with proper structure
        assert all("Properties" in result for result in results)
        assert all("Type" in result for result in results)
        assert all(result["Type"] == "AWS::ECS::Cluster" for result in results)

        # Verify mock calls
        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "ecs")
        mock_proxy.get_paginator.assert_called_once_with("list_clusters", "clusterArns")

        # Verify describe_clusters was called for each page
        assert mock_client.describe_clusters.call_count == 2
        mock_client.describe_clusters.assert_any_call(
            clusters=[
                "arn:aws:ecs:us-west-2:123456789012:cluster/cluster1",
                "arn:aws:ecs:us-west-2:123456789012:cluster/cluster2",
            ],
            include=["TAGS"],
        )
        mock_client.describe_clusters.assert_any_call(
            clusters=["arn:aws:ecs:us-west-2:123456789012:cluster/cluster3"],
            include=["TAGS"],
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.cluster.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty_clusters(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EcsClusterExporter,
    ) -> None:
        """Test paginated resource retrieval with no clusters."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock empty paginator - return the async generator directly
        async def mock_paginate() -> AsyncGenerator[list[str], None]:
            yield []

        # Create an object that has a paginate method returning the async generator
        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[str], None]:
                return mock_paginate()

        # Make sure get_paginator returns our MockPaginator, not a coroutine
        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Mock inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Create options
        options = PaginatedClusterRequest(
            region="us-west-2", account_id="123456789012", include=[]
        )

        # Inspector returns an empty list when given empty clusters
        mock_inspector.inspect.return_value = []

        # Execute and collect results
        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        # Verify
        assert len(results) == 0
        mock_proxy.get_paginator.assert_called_once_with("list_clusters", "clusterArns")
        # describe_clusters should not be called for empty clusters
        mock_client.describe_clusters.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.cluster.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EcsClusterExporter,
    ) -> None:
        """Test that exceptions from inspector are properly propagated."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("Cluster not found")

        # Create options
        options = SingleClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            cluster_name="nonexistent-cluster",
            include=[],
        )

        # Execute and verify exception
        with pytest.raises(Exception, match="Cluster not found"):
            await exporter.get_resource(options)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.cluster.exporter.ResourceInspector")
    async def test_context_manager_cleanup(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EcsClusterExporter,
    ) -> None:
        """Test that context manager cleanup is properly handled."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        # Setup inspector to return a normal result
        mock_inspector = AsyncMock()
        mock_cluster = Cluster(
            Properties=ClusterProperties(
                ClusterName="test-cluster",
                Arn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            ),
        )
        mock_inspector.inspect.return_value = [mock_cluster.dict(exclude_none=True)]
        mock_inspector_class.return_value = mock_inspector

        options = SingleClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            cluster_name="test-cluster",
            include=[],
        )

        # Execute the method
        result = await exporter.get_resource(options)

        # Verify the result is a dictionary with the correct structure
        assert result["Properties"]["ClusterName"] == "test-cluster"
        assert result["Type"] == "AWS::ECS::Cluster"
        assert (
            result["Properties"]["Arn"]
            == "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )

        # Verify the inspector was called correctly
        mock_inspector.inspect.assert_called_once_with(
            [{"clusterName": "test-cluster"}], []
        )

        # Verify the context manager was used correctly (__aenter__ and __aexit__ were called)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "ecs")
        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
