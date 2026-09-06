from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.ecs.service.actions import EcsServiceActionsMap
from aws.core.exporters.ecs.service.models import Service
from aws.core.exporters.ecs.service.models import (
    SingleServiceRequest,
    PaginatedServiceRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.helpers.utils import require_aws_resource
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector
from aws.utils import RegionHelper


class EcsServiceExporter(IResourceExporter[list[str]]):
    _service_name: SupportedServices = "ecs"
    _model_cls: Type[Service] = Service
    _actions_map: Type[EcsServiceActionsMap] = EcsServiceActionsMap

    async def get_resource(self, options: SingleServiceRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single ECS service."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            partition = RegionHelper.get_partition()
            cluster_arn = f"arn:{partition}:ecs:{options.region}:{options.account_id}:cluster/{options.cluster_name}"
            service_arn = f"arn:{partition}:ecs:{options.region}:{options.account_id}:service/{options.cluster_name}/{options.service_name}"

            describe_response = await proxy.client.describe_services(  # type: ignore[attr-defined]
                cluster=cluster_arn,
                services=[service_arn],
                include=["TAGS"],
            )
            require_aws_resource(
                describe_response.get("services"),
                error_code="ServiceNotFoundException",
                message=(
                    f"Service not found: {options.cluster_name}/"
                    f"{options.service_name}"
                ),
                operation_name="DescribeServices",
            )

            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            response = await inspector.inspect(
                [service_arn],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                    "ClusterArn": cluster_arn,
                },
            )

            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedServiceRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all ECS services across all clusters in the region."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            services_paginator = proxy.get_paginator("list_services", "serviceArns")
            clusters_paginator = proxy.get_paginator("list_clusters", "clusterArns")

            async for cluster_arns in clusters_paginator.paginate():
                if cluster_arns:
                    for cluster_arn in cluster_arns:
                        async for services in services_paginator.paginate(
                            cluster=cluster_arn, batch_size=10
                        ):
                            if services:
                                action_result = await inspector.inspect(
                                    services,
                                    options.include,
                                    extra_context={
                                        "AccountId": options.account_id,
                                        "Region": options.region,
                                        "ClusterArn": cluster_arn,
                                    },
                                )
                                yield action_result
