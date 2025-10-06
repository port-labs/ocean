import pytest
from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch
from aws.core.exporters.eks.cluster.exporter import EksClusterExporter
from aws.core.exporters.eks.cluster.models import (
    SingleEksClusterRequest,
    PaginatedEksClusterRequest,
    EksCluster,
    EksClusterProperties,
)


class TestEksClusterExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> EksClusterExporter:
        return EksClusterExporter(mock_session)

    def test_service_name(self, exporter: EksClusterExporter) -> None:
        """Test that the service name is correctly set."""
        assert exporter._service_name == "eks"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        """Test that the exporter initializes correctly."""
        exporter = EksClusterExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.eks.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.eks.cluster.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EksClusterExporter,
    ) -> None:
        """Test successful single resource retrieval."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Create expected EKS cluster response
        expected_cluster = EksCluster(
            Properties=EksClusterProperties(
                name="test-cluster",
                version="1.28",
                roleArn="arn:aws:iam::123456789012:role/EKSClusterRole",
                arn="arn:aws:eks:us-west-2:123456789012:cluster/test-cluster",
                status="ACTIVE",
                endpoint="https://ABC123DEF4567890.gr7.us-west-2.eks.amazonaws.com",
                platformVersion="eks.5",
            ),
        )
        mock_inspector.inspect.return_value = [expected_cluster.dict(exclude_none=True)]

        # Create options
        options = SingleEksClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            cluster_name="test-cluster",
            include=[],
        )

        # Execute
        result = await exporter.get_resource(options)

        # Verify
        assert result == expected_cluster.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "eks")
        mock_inspector.inspect.assert_called_once_with(["test-cluster"], [])

    @pytest.mark.asyncio
    @patch("aws.core.exporters.eks.cluster.exporter.AioBaseClientProxy")
    async def test_get_paginated_resources_success(
        self,
        mock_proxy_class: MagicMock,
        exporter: EksClusterExporter,
    ) -> None:
        """Test successful paginated resource retrieval."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock paginator
        async def mock_paginate() -> AsyncGenerator[list[str], None]:
            yield ["cluster1", "cluster2"]
            yield ["cluster3"]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[str], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Mock describe_cluster response
        def mock_describe_cluster(name: str) -> dict[str, Any]:
            return {
                "cluster": {
                    "name": name,
                    "arn": f"arn:aws:eks:us-west-2:123456789012:cluster/{name}",
                    "version": "1.28",
                    "status": "ACTIVE",
                    "endpoint": f"https://{name}.gr7.us-west-2.eks.amazonaws.com",
                    "roleArn": "arn:aws:iam::123456789012:role/EKSClusterRole",
                    "platformVersion": "eks.5",
                }
            }

        mock_client.describe_cluster.side_effect = mock_describe_cluster

        # Create options
        options = PaginatedEksClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            include=[],
        )

        # Execute and collect results
        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        # Verify
        assert len(results) == 3
        assert all("Properties" in result for result in results)
        assert all("Type" in result for result in results)
        assert all(result["Type"] == "AWS::EKS::Cluster" for result in results)

        # Verify mock calls
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "eks")
        mock_proxy.get_paginator.assert_called_once_with("list_clusters", "clusters")
        assert mock_client.describe_cluster.call_count == 3

    @pytest.mark.asyncio
    @patch("aws.core.exporters.eks.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.eks.cluster.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty_clusters(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EksClusterExporter,
    ) -> None:
        """Test paginated resource retrieval with no clusters."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock empty paginator
        async def mock_paginate() -> AsyncGenerator[list[str], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[str], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Mock inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Create options
        options = PaginatedEksClusterRequest(
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
        mock_proxy.get_paginator.assert_called_once_with("list_clusters", "clusters")
        # describe_cluster should not be called for empty clusters
        mock_client.describe_cluster.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.eks.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.eks.cluster.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EksClusterExporter,
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
        options = SingleEksClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            cluster_name="nonexistent-cluster",
            include=[],
        )

        # Execute and verify exception
        with pytest.raises(Exception, match="Cluster not found"):
            await exporter.get_resource(options)
