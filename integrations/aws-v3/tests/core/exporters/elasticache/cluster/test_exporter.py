from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.elasticache.cluster.exporter import ElastiCacheClusterExporter
from aws.core.exporters.elasticache.cluster.models import (
    SingleCacheClusterRequest,
    PaginatedCacheClusterRequest,
    CacheCluster,
    CacheClusterProperties,
)


class TestElastiCacheClusterExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> ElastiCacheClusterExporter:
        return ElastiCacheClusterExporter(mock_session)

    def test_service_name(self, exporter: ElastiCacheClusterExporter) -> None:
        assert exporter._service_name == "elasticache"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = ElastiCacheClusterExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticache.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.elasticache.cluster.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ElastiCacheClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_client.describe_cache_clusters.return_value = {
            "CacheClusters": [
                {
                    "CacheClusterId": "cluster-1",
                    "CacheNodeType": "cache.t3.micro",
                    "Engine": "redis",
                    "ARN": "arn:aws:elasticache:us-west-2:123456789012:cluster:cluster-1",
                }
            ]
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        cache_cluster = CacheCluster(
            Properties=CacheClusterProperties(
                CacheClusterId="cluster-1",
                CacheNodeType="cache.t3.micro",
                Engine="redis",
            )
        )
        mock_inspector.inspect.return_value = [cache_cluster.dict(exclude_none=True)]

        options = SingleCacheClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            cache_cluster_id="cluster-1",
            include=["ListTagsForResourceAction"],
        )

        result = await exporter.get_resource(options)

        assert result == cache_cluster.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-west-2", "elasticache"
        )
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once()
        call_args = mock_inspector.inspect.call_args
        assert call_args[0][1] == ["ListTagsForResourceAction"]

        call_kwargs = mock_inspector.inspect.call_args[1]
        assert call_kwargs["extra_context"]["AccountId"] == "123456789012"
        assert call_kwargs["extra_context"]["Region"] == "us-west-2"

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticache.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.elasticache.cluster.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ElastiCacheClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client

        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_client.describe_cache_clusters.return_value = {
            "CacheClusters": [
                {
                    "CacheClusterId": "cluster-notexists",
                    "CacheNodeType": "cache.t3.micro",
                    "Engine": "redis",
                    "ARN": "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-notexists",
                }
            ]
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("Cache cluster not found")

        options = SingleCacheClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            cache_cluster_id="cluster-notexists",
            include=[],
        )

        with pytest.raises(Exception, match="Cache cluster not found"):
            await exporter.get_resource(options)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticache.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.elasticache.cluster.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ElastiCacheClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {
                    "CacheClusterId": "cluster-1",
                    "CacheNodeType": "cache.t3.micro",
                    "Engine": "redis",
                },
                {
                    "CacheClusterId": "cluster-2",
                    "CacheNodeType": "cache.t3.small",
                    "Engine": "memcached",
                },
            ]
            yield [
                {
                    "CacheClusterId": "cluster-3",
                    "CacheNodeType": "cache.t3.medium",
                    "Engine": "redis",
                },
            ]

        class MockPaginator:
            def paginate(
                self, **kwargs: Any
            ) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        cluster1 = CacheCluster(
            Properties=CacheClusterProperties(CacheClusterId="cluster-1")
        )
        cluster2 = CacheCluster(
            Properties=CacheClusterProperties(CacheClusterId="cluster-2")
        )
        cluster3 = CacheCluster(
            Properties=CacheClusterProperties(CacheClusterId="cluster-3")
        )

        mock_inspector.inspect.side_effect = [
            [cluster1.dict(exclude_none=True), cluster2.dict(exclude_none=True)],
            [cluster3.dict(exclude_none=True)],
        ]

        options = PaginatedCacheClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            include=["ListTagsForResourceAction"],
        )

        collected: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            collected.extend(page)

        assert len(collected) == 3
        assert collected[0] == cluster1.dict(exclude_none=True)
        assert collected[1] == cluster2.dict(exclude_none=True)
        assert collected[2] == cluster3.dict(exclude_none=True)

        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-east-1", "elasticache"
        )
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_cache_clusters", "CacheClusters"
        )
        assert mock_inspector.inspect.call_count == 2

        calls = mock_inspector.inspect.call_args_list
        for call in calls:
            call_args = call[0]
            call_kwargs = call[1]
            assert call_args[1] == ["ListTagsForResourceAction"]
            assert call_kwargs["extra_context"]["AccountId"] == "123456789012"
            assert call_kwargs["extra_context"]["Region"] == "us-east-1"

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticache.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.elasticache.cluster.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ElastiCacheClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

        class MockPaginator:
            def paginate(
                self, **kwargs: Any
            ) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        options = PaginatedCacheClusterRequest(
            region="us-west-1",
            account_id="123456789012",
            include=[],
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_cache_clusters", "CacheClusters"
        )
        mock_inspector.inspect.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticache.cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.elasticache.cluster.exporter.ResourceInspector")
    async def test_context_manager_cleanup(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ElastiCacheClusterExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        mock_client.describe_cache_clusters.return_value = {
            "CacheClusters": [
                {
                    "CacheClusterId": "cluster-55",
                    "CacheNodeType": "cache.t3.micro",
                    "Engine": "redis",
                    "ARN": "arn:aws:elasticache:us-west-2:123456789012:cluster:cluster-55",
                }
            ]
        }

        mock_inspector = AsyncMock()
        cache_cluster = CacheCluster(
            Properties=CacheClusterProperties(CacheClusterId="cluster-55")
        )
        mock_inspector.inspect.return_value = [cache_cluster.dict(exclude_none=True)]
        mock_inspector_class.return_value = mock_inspector

        options = SingleCacheClusterRequest(
            region="us-west-2",
            account_id="123456789012",
            cache_cluster_id="cluster-55",
            include=[],
        )

        result = await exporter.get_resource(options)
        assert result["Properties"]["CacheClusterId"] == "cluster-55"
        assert result["Type"] == "AWS::ElastiCache::Cluster"

        mock_inspector.inspect.assert_called_once()
        call_args = mock_inspector.inspect.call_args
        assert call_args[0][1] == []

        call_kwargs = mock_inspector.inspect.call_args[1]
        assert call_kwargs["extra_context"]["AccountId"] == "123456789012"
        assert call_kwargs["extra_context"]["Region"] == "us-west-2"

        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-west-2", "elasticache"
        )
        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
