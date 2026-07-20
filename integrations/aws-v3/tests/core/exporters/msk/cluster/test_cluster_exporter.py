from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.msk.cluster.exporter import MskClusterExporter
from aws.core.exporters.msk.cluster.models import (
    SingleMskClusterRequest,
    PaginatedMskClusterRequest,
    MskCluster,
    MskClusterProperties,
)


class TestMskClusterExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> MskClusterExporter:
        return MskClusterExporter(mock_session)

    def test_service_name(self, exporter: MskClusterExporter) -> None:
        assert exporter._service_name == "kafka"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = MskClusterExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.msk.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.msk.cluster.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: MskClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        cluster_info = {
            "ClusterArn": "arn:aws:kafka:us-west-2:123456789012:cluster/test-cluster/abc123",
            "ClusterName": "test-cluster",
            "State": "ACTIVE",
            "NumberOfBrokerNodes": 3,
        }
        mock_client.describe_cluster.return_value = {"ClusterInfo": cluster_info}

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        expected_cluster = MskCluster(
            Properties=MskClusterProperties(
                ClusterArn="arn:aws:kafka:us-west-2:123456789012:cluster/test-cluster/abc123",
                ClusterName="test-cluster",
                State="ACTIVE",
                NumberOfBrokerNodes=3,
            ),
        )
        mock_inspector.inspect.return_value = [expected_cluster.dict(exclude_none=True)]

        options = SingleMskClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            cluster_arn="arn:aws:kafka:us-west-2:123456789012:cluster/test-cluster/abc123",
            include=[],
        )

        result = await exporter.get_resource(options)

        assert result == expected_cluster.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "kafka")
        mock_client.describe_cluster.assert_called_once_with(
            ClusterArn="arn:aws:kafka:us-west-2:123456789012:cluster/test-cluster/abc123"
        )
        mock_inspector.inspect.assert_called_once_with([cluster_info], [])

    @pytest.mark.asyncio
    @patch("aws.core.exporters.msk.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.msk.cluster.exporter.ResourceInspector")
    async def test_get_resource_empty_response(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: MskClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_client.describe_cluster.return_value = {"ClusterInfo": {}}

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        options = SingleMskClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            cluster_arn="arn:aws:kafka:us-west-2:123456789012:cluster/nonexistent/xyz",
            include=[],
        )

        result = await exporter.get_resource(options)

        assert result == {}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.msk.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.msk.cluster.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: MskClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        clusters_page1 = [
            {
                "ClusterArn": "arn:aws:kafka:us-west-2:123456789012:cluster/cluster1/abc",
                "ClusterName": "cluster1",
                "State": "ACTIVE",
            },
            {
                "ClusterArn": "arn:aws:kafka:us-west-2:123456789012:cluster/cluster2/def",
                "ClusterName": "cluster2",
                "State": "ACTIVE",
            },
        ]
        clusters_page2 = [
            {
                "ClusterArn": "arn:aws:kafka:us-west-2:123456789012:cluster/cluster3/ghi",
                "ClusterName": "cluster3",
                "State": "CREATING",
            },
        ]

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield clusters_page1
            yield clusters_page2

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = [
            [
                {
                    "Type": "AWS::MSK::Cluster",
                    "Properties": {"ClusterName": "cluster1"},
                },
                {
                    "Type": "AWS::MSK::Cluster",
                    "Properties": {"ClusterName": "cluster2"},
                },
            ],
            [
                {
                    "Type": "AWS::MSK::Cluster",
                    "Properties": {"ClusterName": "cluster3"},
                },
            ],
        ]

        options = PaginatedMskClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            include=[],
        )

        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert len(results) == 3
        assert all("Properties" in result for result in results)
        assert all("Type" in result for result in results)
        assert all(result["Type"] == "AWS::MSK::Cluster" for result in results)

        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "kafka")
        mock_proxy.get_paginator.assert_called_once_with(
            "list_clusters", "ClusterInfoList"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.msk.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.msk.cluster.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty_clusters(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: MskClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        options = PaginatedMskClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            include=[],
        )

        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert len(results) == 0
        mock_proxy.get_paginator.assert_called_once_with(
            "list_clusters", "ClusterInfoList"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.msk.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.msk.cluster.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: MskClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_client.describe_cluster.return_value = {"ClusterInfo": {}}

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("Cluster not found")

        options = SingleMskClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            cluster_arn="arn:aws:kafka:us-west-2:123456789012:cluster/nonexistent/xyz",
            include=[],
        )

        with pytest.raises(Exception, match="Cluster not found"):
            await exporter.get_resource(options)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.msk.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.msk.cluster.exporter.ResourceInspector")
    async def test_context_manager_cleanup(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: MskClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        cluster_info = {
            "ClusterArn": "arn:aws:kafka:us-west-2:123456789012:cluster/test-cluster/abc",
            "ClusterName": "test-cluster",
        }
        mock_client.describe_cluster.return_value = {"ClusterInfo": cluster_info}

        mock_inspector = AsyncMock()
        mock_cluster = MskCluster(
            Properties=MskClusterProperties(
                ClusterArn="arn:aws:kafka:us-west-2:123456789012:cluster/test-cluster/abc",
                ClusterName="test-cluster",
            ),
        )
        mock_inspector.inspect.return_value = [mock_cluster.dict(exclude_none=True)]
        mock_inspector_class.return_value = mock_inspector

        options = SingleMskClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            cluster_arn="arn:aws:kafka:us-west-2:123456789012:cluster/test-cluster/abc",
            include=[],
        )

        result = await exporter.get_resource(options)

        assert result["Properties"]["ClusterName"] == "test-cluster"
        assert result["Type"] == "AWS::MSK::Cluster"

        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "kafka")
        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
