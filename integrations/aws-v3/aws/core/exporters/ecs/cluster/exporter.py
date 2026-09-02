from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.helpers.utils import require_aws_resource
from aws.core.exporters.ecs.cluster.actions import EcsClusterActionsMap
from aws.core.exporters.ecs.cluster.models import Cluster
from aws.core.exporters.ecs.cluster.models import (
    SingleClusterRequest,
    PaginatedClusterRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class EcsClusterExporter(IResourceExporter[list[str]]):
    _service_name: SupportedServices = "ecs"
    _model_cls: Type[Cluster] = Cluster
    _actions_map: Type[EcsClusterActionsMap] = EcsClusterActionsMap

    async def get_resource(self, options: SingleClusterRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single ECS cluster."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            # Live-event single-cluster fetch only has a cluster name from CloudTrail.
            # describe_clusters returns an empty list when the cluster is gone instead
            # of raising, and the inspector would still build a stub from that name.
            # Confirm it exists so a missing cluster raises and the live-event handler
            # can treat the update as a delete instead.
            response = await proxy.client.describe_clusters(  # type: ignore[attr-defined]
                clusters=[options.cluster_name]
            )
            require_aws_resource(
                response.get("clusters"),
                error_code="ClusterNotFoundException",
                message=f"Cluster not found: {options.cluster_name}",
                operation_name="DescribeClusters",
            )

            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [options.cluster_name],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )

            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedClusterRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all ECS clusters in the region."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("list_clusters", "clusterArns")

            async for clusters in paginator.paginate():
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
