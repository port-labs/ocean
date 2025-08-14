from aws.core.interfaces.exporter import IResourceExporter
from aws.core.exporters.ecs.cluster.options import (
    SingleECSClusterExporterOptions,
    PaginatedECSClusterExporterOptions,
)
from aws.core.helpers.types import SupportedServices
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.ecs.cluster.inspector import ECSClusterInspector
from typing import Any, AsyncGenerator
from aws.core.exporters.ecs.cluster.models import ECSCluster


class ECSClusterExporter(IResourceExporter):
    SERVICE_NAME: SupportedServices = "ecs"

    async def get_resource(
        self, options: SingleECSClusterExporterOptions
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single ECS cluster."""

        async with AioBaseClientProxy(
            self.session, options.region, self.SERVICE_NAME
        ) as proxy:
            inspector = ECSClusterInspector(proxy.client)
            response: ECSCluster = await inspector.inspect(
                options.cluster_arn, options.include
            )

            return response.dict()

    async def get_paginated_resources(
        self, options: PaginatedECSClusterExporterOptions
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield pages of ECS cluster information, fetched using pagination."""

        async with AioBaseClientProxy(
            self.session, options.region, self.SERVICE_NAME
        ) as proxy:
            inspector = ECSClusterInspector(proxy.client)
            paginator = proxy.get_paginator("list_clusters", "clusterArns")

            from loguru import logger

            try:
                async for cluster_arns in paginator.paginate():
                    if not cluster_arns:
                        continue

                    clusters: list[ECSCluster] = await inspector.inspect_batch(
                        cluster_arns, options.include
                    )
                    results = [cluster.dict(exclude_none=True) for cluster in clusters]
                    yield results
            except Exception as e:
                logger.error(f"Error during ECS cluster pagination: {e}")
                raise
