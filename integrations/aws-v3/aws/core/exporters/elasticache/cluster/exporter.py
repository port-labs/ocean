from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.elasticache.cluster.actions import ElastiCacheClusterActionsMap
from aws.core.exporters.elasticache.cluster.models import CacheCluster
from aws.core.exporters.elasticache.cluster.models import (
    SingleCacheClusterRequest,
    PaginatedCacheClusterRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class ElastiCacheClusterExporter(IResourceExporter):
    _service_name: SupportedServices = "elasticache"
    _model_cls: Type[CacheCluster] = CacheCluster
    _actions_map: Type[ElastiCacheClusterActionsMap] = ElastiCacheClusterActionsMap

    async def get_resource(self, options: SingleCacheClusterRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single ElastiCache cluster."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            response = await proxy.client.describe_cache_clusters(  # type: ignore[attr-defined]
                CacheClusterId=options.cache_cluster_id,
                ShowCacheNodeInfo=True,
            )

            cache_clusters = response["CacheClusters"]
            action_result = await inspector.inspect(
                cache_clusters,
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return action_result[0] if action_result else {}

    async def get_paginated_resources(
        self, options: PaginatedCacheClusterRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all ElastiCache clusters in the region."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator(
                "describe_cache_clusters",
                "CacheClusters",
            )

            async for cache_clusters in paginator.paginate(ShowCacheNodeInfo=True):
                if cache_clusters:
                    action_result = await inspector.inspect(
                        cache_clusters,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
