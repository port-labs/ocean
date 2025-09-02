from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.ecs.cluster.actions import (
    ECSClusterSingleActionsMap,
    ECSClusterBatchActionsMap,
)
from aws.core.exporters.ecs.cluster.models import ECSCluster
from aws.core.exporters.ecs.cluster.models import (
    SingleECSClusterRequest,
    PaginatedECSClusterRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import (
    SingleResourceInspector,
    BatchResourceInspector,
)


class ECSClusterExporter(IResourceExporter):
    _service_name: SupportedServices = "ecs"
    _model_cls: Type[ECSCluster] = ECSCluster
    _single_actions_map: Type[ECSClusterSingleActionsMap] = ECSClusterSingleActionsMap
    _batch_actions_map: Type[ECSClusterBatchActionsMap] = ECSClusterBatchActionsMap

    async def get_resource(self, options: SingleECSClusterRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single ECS cluster."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:

            inspector = SingleResourceInspector(
                proxy.client,
                self._single_actions_map(),
                lambda: self._model_cls(),
                self.account_id,
                options.region,
            )
            response = await inspector.inspect(options.cluster_arn, options.include)

            return response.dict(exclude_none=True)

    async def get_paginated_resources(
        self, options: PaginatedECSClusterRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield pages of ECS cluster information with automatic batch optimization."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = BatchResourceInspector(
                proxy.client,
                self._batch_actions_map(),
                lambda: self._model_cls(),
                self.account_id,
                options.region,
            )
            paginator = proxy.get_paginator("list_clusters", "clusterArns")

            async for cluster_arns in paginator.paginate():
                if not cluster_arns:
                    continue

                clusters = await inspector.inspect_batch(cluster_arns, options.include)
                yield [cluster.dict(exclude_none=True) for cluster in clusters]
