from typing import Optional

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.exporters.base import BaseExporter
from azure_integration.helpers.queries import RESOURCE_CONTAINERS_QUERY
from azure_integration.models import (
    ResourceContainerExporterOptions,
    ResourceGroupTagFilters,
)
from azure_integration.utils import build_rg_tag_filter_clause


class ResourceContainersExporter(BaseExporter):
    async def get_paginated_resources(
        self, options: ResourceContainerExporterOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        query = self._build_sync_query(options.tag_filter)
        async for sub_batch in self.sub_manager.get_sub_id_in_batches():
            logger.info(
                f"Exporting container resources for {len(sub_batch)} subscriptions"
            )
            async for resource_containers in self.client.make_paginated_request(
                query,
                sub_batch,
            ):
                if resource_containers:
                    logger.info(
                        f"Received batch of {len(resource_containers)} resource containers"
                    )
                    yield resource_containers
                else:
                    logger.info("No containers found in this batch")
                    continue

    def _build_sync_query(
        self, tag_filters: Optional[ResourceGroupTagFilters] = None
    ) -> str:
        rg_tag_filter_clause = (
            build_rg_tag_filter_clause(tag_filters) if tag_filters else ""
        )
        query = RESOURCE_CONTAINERS_QUERY.format(rg_tag_filter_clause)
        return query
