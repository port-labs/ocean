import pytest
from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch
from aws.core.exporters.ecs.service.exporter import EcsServiceExporter
from aws.core.exporters.ecs.service.models import (
    SingleServiceRequest,
    PaginatedServiceRequest,
)


class TestEcsServiceExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AioSession for testing."""
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> EcsServiceExporter:
        """Create an EcsServiceExporter instance for testing."""
        return EcsServiceExporter(mock_session)

    def test_service_name(self, exporter: EcsServiceExporter) -> None:
        """Test that the service name is correctly set."""
        assert exporter._service_name == "ecs"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        """Test that the exporter initializes correctly."""
        exporter = EcsServiceExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._service_name == "ecs"

    @pytest.mark.asyncio
    async def test_get_resource_single_service(
        self, exporter: EcsServiceExporter
    ) -> None:
        """Test fetching a single ECS service."""
        options = SingleServiceRequest(
            service_name="test-service",
            cluster_name="test-cluster",
            region="us-east-1",
            account_id="123456789012",
        )

        mock_service_data = {
            "serviceName": "test-service",
            "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service",
            "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster",
            "status": "ACTIVE",
            "desiredCount": 2,
            "runningCount": 2,
        }

        with patch(
            "aws.core.exporters.ecs.service.exporter.AioBaseClientProxy"
        ) as mock_proxy_class:
            mock_proxy = AsyncMock()
            mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

            mock_inspector = AsyncMock()
            mock_inspector.inspect.return_value = [mock_service_data]

            with patch(
                "aws.core.exporters.ecs.service.exporter.ResourceInspector",
                return_value=mock_inspector,
            ):
                result = await exporter.get_resource(options)

        assert result == mock_service_data
        mock_inspector.inspect.assert_called_once()

        # Verify the service ARN was constructed correctly
        call_args = mock_inspector.inspect.call_args[0][0]
        assert len(call_args) == 1
        assert (
            call_args[0]["serviceArn"]
            == "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service"
        )
        assert (
            call_args[0]["clusterArn"]
            == "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster"
        )

    @pytest.mark.asyncio
    async def test_get_resource_empty_response(
        self, exporter: EcsServiceExporter
    ) -> None:
        """Test handling empty response from inspector."""
        options = SingleServiceRequest(
            service_name="nonexistent-service",
            cluster_name="test-cluster",
            region="us-east-1",
            account_id="123456789012",
        )

        with patch(
            "aws.core.exporters.ecs.service.exporter.AioBaseClientProxy"
        ) as mock_proxy_class:
            mock_proxy = AsyncMock()
            mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

            mock_inspector = AsyncMock()
            mock_inspector.inspect.return_value = []

            with patch(
                "aws.core.exporters.ecs.service.exporter.ResourceInspector",
                return_value=mock_inspector,
            ):
                result = await exporter.get_resource(options)

        assert result == {}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.service.exporter.EcsClusterExporter")
    @patch("aws.core.exporters.ecs.service.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.service.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        mock_cluster_exporter_class: MagicMock,
        exporter: EcsServiceExporter,
    ) -> None:
        """Test successful paginated resource fetching."""
        # Setup cluster exporter mock
        mock_cluster_exporter = AsyncMock()
        mock_cluster_exporter_class.return_value = mock_cluster_exporter

        # Mock cluster data
        mock_clusters = [
            {
                "Properties": {
                    "ClusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/cluster1"
                }
            }
        ]

        # Mock the get_paginated_resources method to return an async generator
        async def mock_cluster_generator(
            options: Any,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield mock_clusters

        mock_cluster_exporter.get_paginated_resources = mock_cluster_generator

        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock service pagination
        async def mock_service_paginate() -> AsyncGenerator[list[str], None]:
            yield [
                "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service1",
                "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service2",
            ]

        class MockServicePaginator:
            def paginate(self, cluster: Any = None) -> AsyncGenerator[list[str], None]:
                return mock_service_paginate()

        # Use MagicMock for get_paginator to avoid coroutine issues
        mock_proxy.get_paginator = MagicMock(return_value=MockServicePaginator())

        # Setup inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        mock_service_details = [
            {
                "serviceName": "service1",
                "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service1",
                "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/cluster1",
                "status": "ACTIVE",
            },
            {
                "serviceName": "service2",
                "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service2",
                "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/cluster1",
                "status": "ACTIVE",
            },
        ]

        mock_inspector.inspect.return_value = mock_service_details

        # Execute
        options = PaginatedServiceRequest(
            region="us-east-1",
            account_id="123456789012",
        )

        results = []
        async for result in exporter.get_paginated_resources(options):
            results.extend(result)

        # Verify
        assert len(results) == 2
        assert results[0]["serviceName"] == "service1"
        assert results[1]["serviceName"] == "service2"

        # Verify service identifiers were constructed correctly
        call_args = mock_inspector.inspect.call_args[0][0]
        assert len(call_args) == 2
        assert (
            call_args[0]["serviceArn"]
            == "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service1"
        )
        assert (
            call_args[0]["clusterArn"]
            == "arn:aws:ecs:us-east-1:123456789012:cluster/cluster1"
        )
