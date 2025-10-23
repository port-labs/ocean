from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.exporters.base import BaseExporter
from azure_integration.options import (
    ResourceGraphExporterOptions,
)
from azure_integration.helpers.utils import format_query
from azure_integration.clients.base import AzureRequest


class ResourceGraphExporter(BaseExporter):

    async def get_paginated_resources(
        self, options: ResourceGraphExporterOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        query = format_query(options.query)
        logger.info(
            f"Exporting graph resources for {len(options.subscriptions)} subscriptions with query: {query}"
        )

        request = AzureRequest(
            endpoint="providers/Microsoft.ResourceGraph/resources",
            json_data={"query": query, "subscriptions": options.subscriptions},
            method="POST",
            api_version="2024-04-01",
            data_key="data",
        )

        async for results in self.client.make_paginated_request(request):
            if results:
                logger.info(f"Received batch of {len(results)} results")
                yield results
