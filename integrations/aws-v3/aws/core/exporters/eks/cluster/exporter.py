from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.eks.cluster.actions import EksClusterActionsMap
from aws.core.exporters.eks.cluster.models import EksCluster
from aws.core.exporters.eks.cluster.models import (
    SingleEksClusterRequest,
    PaginatedEksClusterRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class EksClusterExporter(IResourceExporter):
    _service_name: SupportedServices = "eks"
    _model_cls: Type[EksCluster] = EksCluster
    _actions_map: Type[EksClusterActionsMap] = EksClusterActionsMap

    async def get_resource(self, options: SingleEksClusterRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single EKS cluster."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:

            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect([options.cluster_name], options.include)

            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedEksClusterRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all EKS clusters in the region."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("list_clusters", "clusters")

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
