from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.msk.serverless_cluster.actions import (
    MskServerlessClusterActionsMap,
)
from aws.core.exporters.msk.serverless_cluster.models import (
    MskServerlessCluster,
    SingleMskServerlessClusterRequest,
    PaginatedMskServerlessClusterRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class MskServerlessClusterExporter(IResourceExporter):
    _service_name: SupportedServices = "kafka"
    _model_cls: Type[MskServerlessCluster] = MskServerlessCluster
    _actions_map: Type[MskServerlessClusterActionsMap] = MskServerlessClusterActionsMap

    async def get_resource(
        self, options: SingleMskServerlessClusterRequest
    ) -> dict[str, Any]:
        """Fetch a single MSK serverless cluster by ARN."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await proxy.client.describe_cluster_v2(  # type: ignore[attr-defined]
                ClusterArn=options.cluster_arn
            )
            cluster = response["ClusterInfo"]
            action_result = await inspector.inspect(
                [cluster],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return action_result[0] if action_result else {}

    async def get_paginated_resources(
        self, options: PaginatedMskServerlessClusterRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all MSK serverless clusters in the region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("list_clusters_v2", "ClusterInfoList")

            async for clusters in paginator.paginate(ClusterTypeFilter="SERVERLESS"):
                if clusters:
                    action_result = await inspector.inspect(
                        clusters,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
