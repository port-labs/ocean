from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.eks.nodegroup.actions import (
    EksNodegroupActionsMap,
    NodegroupRecord,
)
from aws.core.exporters.eks.nodegroup.models import EksNodegroup
from aws.core.exporters.eks.nodegroup.models import (
    SingleEksNodegroupRequest,
    PaginatedEksNodegroupRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class EksNodegroupExporter(IResourceExporter[list[NodegroupRecord]]):
    _service_name: SupportedServices = "eks"
    _model_cls: Type[EksNodegroup] = EksNodegroup
    _actions_map: Type[EksNodegroupActionsMap] = EksNodegroupActionsMap

    async def get_resource(self, options: SingleEksNodegroupRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single EKS nodegroup."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            # Confirm the nodegroup exists so a live-event handler can treat
            # a missing nodegroup as a delete rather than an empty upsert.
            await proxy.client.describe_nodegroup(  # type: ignore[attr-defined]
                clusterName=options.cluster_name,
                nodegroupName=options.nodegroup_name,
            )

            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [
                    NodegroupRecord(
                        clusterName=options.cluster_name,
                        nodegroupName=options.nodegroup_name,
                    )
                ],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )

            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedEksNodegroupRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all EKS nodegroups across all clusters in the region."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            clusters_paginator = proxy.get_paginator("list_clusters", "clusters")
            nodegroups_paginator = proxy.get_paginator("list_nodegroups", "nodegroups")

            async for cluster_names in clusters_paginator.paginate():
                if not cluster_names:
                    continue
                for cluster_name in cluster_names:
                    async for nodegroup_names in nodegroups_paginator.paginate(
                        clusterName=cluster_name
                    ):
                        if nodegroup_names:
                            records: list[NodegroupRecord] = [
                                NodegroupRecord(
                                    clusterName=cluster_name,
                                    nodegroupName=name,
                                )
                                for name in nodegroup_names
                            ]
                            action_result = await inspector.inspect(
                                records,
                                options.include,
                                extra_context={
                                    "AccountId": options.account_id,
                                    "Region": options.region,
                                },
                            )
                            yield action_result
                        else:
                            yield []
