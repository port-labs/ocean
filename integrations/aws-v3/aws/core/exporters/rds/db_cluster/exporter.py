from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.rds.db_cluster.actions import RdsDbClusterActionsMap
from aws.core.exporters.rds.db_cluster.models import (
    DbCluster,
    SingleDbClusterRequest,
    PaginatedDbClusterRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class RdsDbClusterExporter(IResourceExporter):
    _service_name: SupportedServices = "rds"
    _model_cls: Type[DbCluster] = DbCluster
    _actions_map: Type[RdsDbClusterActionsMap] = RdsDbClusterActionsMap

    async def get_resource(self, options: SingleDbClusterRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single RDS DB cluster."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            response = await proxy.client.describe_db_clusters(  # type: ignore[attr-defined]
                DBClusterIdentifier=options.db_cluster_identifier
            )

            db_cluster = response["DBClusters"]
            action_result = await inspector.inspect(
                db_cluster,
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return action_result[0] if action_result else {}

    async def get_paginated_resources(
        self, options: PaginatedDbClusterRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all RDS DB clusters in the region."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("describe_db_clusters", "DBClusters")

            async for db_clusters in paginator.paginate():
                if db_clusters:
                    action_result = await inspector.inspect(
                        db_clusters,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
