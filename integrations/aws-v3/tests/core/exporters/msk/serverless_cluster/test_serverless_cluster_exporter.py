import pytest
from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch
from aws.core.exporters.msk.serverless_cluster.exporter import (
    MskServerlessClusterExporter,
)
from aws.core.exporters.msk.serverless_cluster.models import (
    MskServerlessCluster,
    MskServerlessClusterProperties,
    SingleMskServerlessClusterRequest,
    PaginatedMskServerlessClusterRequest,
)

CLUSTER_ARN = "arn:aws:kafka:us-east-1:123456789012:cluster/test-cluster/abc123"

SAMPLE_CLUSTER_INFO: dict[str, Any] = {
    "ClusterArn": CLUSTER_ARN,
    "ClusterName": "test-cluster",
    "ClusterType": "SERVERLESS",
    "State": "ACTIVE",
    "CurrentVersion": "K3AEGXETSR30VB",
    "Tags": {"env": "prod"},
    "Serverless": {
        "VpcConfigs": [{"SubnetIds": ["subnet-aaa"], "SecurityGroupIds": ["sg-bbb"]}],
        "ClientAuthentication": {"Sasl": {"Iam": {"Enabled": True}}},
        "ConnectivityInfo": {"NetworkType": "IPV4"},
    },
}


class TestMskServerlessClusterExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> MskServerlessClusterExporter:
        return MskServerlessClusterExporter(mock_session)

    def test_service_name(self, exporter: MskServerlessClusterExporter) -> None:
        assert exporter._service_name == "kafka"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = MskServerlessClusterExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.msk.serverless_cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.msk.serverless_cluster.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: MskServerlessClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.describe_cluster_v2.return_value = {
            "ClusterInfo": SAMPLE_CLUSTER_INFO
        }

        expected = MskServerlessCluster(
            Properties=MskServerlessClusterProperties(
                clusterArn=CLUSTER_ARN,
                clusterName="test-cluster",
                clusterType="SERVERLESS",
                state="ACTIVE",
                currentVersion="K3AEGXETSR30VB",
                tags={"env": "prod"},
                serverless=SAMPLE_CLUSTER_INFO["Serverless"],
            )
        )
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = [expected.dict(exclude_none=True)]

        options = SingleMskServerlessClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            cluster_arn=CLUSTER_ARN,
            include=[],
        )

        result = await exporter.get_resource(options)

        assert result == expected.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "kafka")
        mock_client.describe_cluster_v2.assert_called_once_with(ClusterArn=CLUSTER_ARN)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.msk.serverless_cluster.exporter.AioBaseClientProxy")
    async def test_get_paginated_resources_success(
        self,
        mock_proxy_class: MagicMock,
        exporter: MskServerlessClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        second_cluster: dict[str, Any] = {
            **SAMPLE_CLUSTER_INFO,
            "ClusterName": "cluster-b",
        }

        async def mock_paginate(
            **kwargs: Any,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            assert kwargs.get("ClusterTypeFilter") == "SERVERLESS"
            yield [SAMPLE_CLUSTER_INFO, second_cluster]

        class MockPaginator:
            def paginate(
                self, **kwargs: Any
            ) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate(**kwargs)

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        options = PaginatedMskServerlessClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            include=[],
        )

        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert len(results) == 2
        assert all("Properties" in r for r in results)
        assert all(r["Type"] == "AWS::MSK::ServerlessCluster" for r in results)
        mock_proxy.get_paginator.assert_called_once_with(
            "list_clusters_v2", "ClusterInfoList"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.msk.serverless_cluster.exporter.AioBaseClientProxy")
    async def test_get_paginated_resources_empty(
        self,
        mock_proxy_class: MagicMock,
        exporter: MskServerlessClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate(**kwargs: Any) -> AsyncGenerator[list[Any], None]:
            yield []

        class MockPaginator:
            def paginate(self, **kwargs: Any) -> AsyncGenerator[list[Any], None]:
                return mock_paginate(**kwargs)

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        options = PaginatedMskServerlessClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            include=[],
        )

        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []

    @pytest.mark.asyncio
    @patch("aws.core.exporters.msk.serverless_cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.msk.serverless_cluster.exporter.ResourceInspector")
    async def test_get_resource_propagates_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: MskServerlessClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.describe_cluster_v2.side_effect = Exception("Cluster not found")
        mock_inspector_class.return_value = AsyncMock()

        options = SingleMskServerlessClusterRequest(
            region="us-east-1",
            account_id="000000000000",
            cluster_arn="arn:aws:kafka:us-east-1:000000000000:cluster/ghost/xyz",
            include=[],
        )

        with pytest.raises(Exception, match="Cluster not found"):
            await exporter.get_resource(options)
