from typing import Optional

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.helpers.queries import RESOURCES_QUERY
from azure_integration.models import ResourceExporterOptions, ResourceGroupTagFilters
from azure_integration.utils import build_rg_tag_filter_clause

from .base import BaseExporter


class ResourcesExporter(BaseExporter):
    async def get_paginated_resources(
        self, options: ResourceExporterOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        resource_types = options.resource_types
        tag_filters = options.tag_filter
        query = self._build_full_sync_query(resource_types, tag_filters)
        async for sub_batch in self.sub_manager.get_sub_id_in_batches():
            logger.info(f"Exporting resources for {len(sub_batch)} subscriptions")
            async for resources in self.client.make_paginated_request(query, sub_batch):
                if resources:
                    logger.info(f"Received batch of {len(resources)} resource")
                    yield resources
                else:
                    logger.info("No resources found in this batch")
                    continue

    def _build_full_sync_query(
        self,
        resource_types: list[str] | None = None,
        tag_filters: Optional[ResourceGroupTagFilters] = None,
    ) -> str:
        resource_filter_clause = ""
        if resource_types:
            lower_resource_types = [f"'{rt.lower()}'" for rt in resource_types]
            resource_types_filter = ", ".join(lower_resource_types)
            resource_filter_clause = f"| where type in~ ({resource_types_filter})"

        rg_tag_filter_clause = (
            build_rg_tag_filter_clause(tag_filters, tag_key_name="rgTags")
            if tag_filters
            else ""
        )
        query = RESOURCES_QUERY.format(resource_filter_clause, rg_tag_filter_clause)

        return query
