from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.ecs.cluster.exporter import ECSClusterExporter
from aws.core.exporters.ecs.cluster.models import (
    ECSCluster,
    ECSClusterProperties,
    SingleECSClusterRequest,
    PaginatedECSClusterRequest,
)


class TestECSClusterExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AioSession for testing."""
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> ECSClusterExporter:
        """Create an ECSClusterExporter instance for testing."""
        return ECSClusterExporter(mock_session, "test-account-id")

    def test_service_name(self, exporter: ECSClusterExporter) -> None:
        """Test that the service name is correctly set."""
        assert exporter._service_name == "ecs"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        """Test that the exporter initializes correctly."""
        exporter = ECSClusterExporter(mock_session, "test-account-id")
        assert exporter.session == mock_session

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.cluster.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ECSClusterExporter,
    ) -> None:
        """Test successful single resource retrieval."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Create expected ECSCluster response
        expected_cluster = ECSCluster(
            Properties=ECSClusterProperties(
                clusterArn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
                clusterName="test-cluster",
                status="ACTIVE",
                tags=[{"key": "Environment", "value": "test"}],
            ),
        )
        mock_inspector.inspect.return_value = expected_cluster

        # Create options
        options = SingleECSClusterRequest(
            region="us-west-2",
            cluster_arn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            include=["GetClusterPendingTasksAction"],
        )

        # Execute
        result = await exporter.get_resource(options)

        # Verify
        assert result == expected_cluster.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "ecs")
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once_with(
            "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            ["GetClusterPendingTasksAction"],
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.cluster.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ECSClusterExporter,
    ) -> None:
        """Test successful paginated resource retrieval with batch optimization."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Mock paginator - return the async generator directly
        cluster_arns = [
            "arn:aws:ecs:us-west-2:123456789012:cluster/cluster-1",
            "arn:aws:ecs:us-west-2:123456789012:cluster/cluster-2",
        ]

        async def mock_paginate() -> AsyncGenerator[list[str], None]:
            yield cluster_arns

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[str], None]:
                return mock_paginate()

        # Make sure get_paginator returns our MockPaginator, not a coroutine
        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Mock inspector results - now returns a list for batch operations
        expected_clusters = [
            ECSCluster(
                Properties=ECSClusterProperties(
                    clusterArn=cluster_arns[0], clusterName="cluster-1"
                )
            ),
            ECSCluster(
                Properties=ECSClusterProperties(
                    clusterArn=cluster_arns[1], clusterName="cluster-2"
                )
            ),
        ]
        mock_inspector.inspect_batch.return_value = expected_clusters

        # Create options
        options = PaginatedECSClusterRequest(
            region="us-west-2",
            include=["GetClusterPendingTasksAction"],
        )

        # Execute
        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.extend(batch)

        # Verify
        assert len(results) == 2
        assert results[0]["Properties"]["clusterArn"] == cluster_arns[0]
        assert results[1]["Properties"]["clusterArn"] == cluster_arns[1]

        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "ecs")
        mock_proxy.get_paginator.assert_called_once_with("list_clusters", "clusterArns")

        # Verify the inspector was called with the full list for batch optimization
        mock_inspector.inspect_batch.assert_called_once_with(
            cluster_arns, ["GetClusterPendingTasksAction"]
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.cluster.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty_page(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ECSClusterExporter,
    ) -> None:
        """Test pagination with empty page."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Mock empty paginator - return the async generator directly
        async def mock_paginate() -> AsyncGenerator[list[str], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[str], None]:
                return mock_paginate()

        # Make sure get_paginator returns our MockPaginator, not a coroutine
        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Create options
        options = PaginatedECSClusterRequest(
            region="us-west-2",
            include=[],
        )

        # Execute
        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.extend(batch)

        # Verify no results
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.cluster.exporter.ResourceInspector")
    async def test_get_paginated_resources_with_include(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ECSClusterExporter,
    ) -> None:
        """Test pagination with include actions using batch optimization."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Mock paginator - return the async generator directly
        cluster_arns = ["arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"]

        async def mock_paginate() -> AsyncGenerator[list[str], None]:
            yield cluster_arns

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[str], None]:
                return mock_paginate()

        # Make sure get_paginator returns our MockPaginator, not a coroutine
        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Mock inspector results
        expected_cluster = ECSCluster(
            Properties=ECSClusterProperties(
                clusterArn=cluster_arns[0],
                clusterName="test-cluster",
                pendingTaskArns=[
                    "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
                ],
            )
        )
        mock_inspector.inspect_batch.return_value = [expected_cluster]

        # Create options
        options = PaginatedECSClusterRequest(
            region="us-west-2",
            include=["GetClusterPendingTasksAction"],
        )

        # Execute
        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.extend(batch)

        # Verify
        assert len(results) == 1
        assert results[0]["Properties"]["clusterArn"] == cluster_arns[0]
        assert results[0]["Properties"]["pendingTaskArns"] == [
            "arn:aws:ecs:us-west-2:123456789012:task/test-cluster/task-1"
        ]

        # Verify inspector was called with the full list for batch optimization
        mock_inspector.inspect_batch.assert_called_once_with(
            cluster_arns, ["GetClusterPendingTasksAction"]
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.cluster.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ECSClusterExporter,
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
        options = SingleECSClusterRequest(
            region="us-west-2",
            cluster_arn="arn:aws:ecs:us-west-2:123456789012:cluster/nonexistent-cluster",
            include=["GetClusterPendingTasksAction"],
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
        exporter: ECSClusterExporter,
    ) -> None:
        """Test that context manager cleanup is properly handled."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        # Setup inspector to return a normal result
        mock_inspector = AsyncMock()
        mock_cluster = ECSCluster(
            Properties=ECSClusterProperties(
                clusterArn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
                clusterName="test-cluster",
            ),
        )
        mock_inspector.inspect.return_value = mock_cluster
        mock_inspector_class.return_value = mock_inspector

        options = SingleECSClusterRequest(
            region="us-west-2",
            cluster_arn="arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster",
            include=[],
        )

        # Execute the method
        result = await exporter.get_resource(options)

        # Verify the result is a dictionary with the correct structure
        assert (
            result["Properties"]["clusterArn"]
            == "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster"
        )
        assert result["Type"] == "AWS::ECS::Cluster"
        assert result["Properties"]["clusterName"] == "test-cluster"

        # Verify the inspector was called correctly
        mock_inspector.inspect.assert_called_once_with(
            "arn:aws:ecs:us-west-2:123456789012:cluster/test-cluster", []
        )

        # Verify the context manager was used correctly (__aenter__ and __aexit__ were called)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "ecs")
        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
