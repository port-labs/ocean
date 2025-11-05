from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from azure_integration.exporters.base import BaseExporter
from azure_integration.options import (
    ResourceGraphExporterOptions,
)
from azure_integration.helpers.http import format_query
from azure_integration.clients.base import AzureRequest


_SUBCRIPTION_BATCH_SIZE = 100
_MAX_CONCURRENT_REQUESTS = 10


class ResourceGraphExporter(BaseExporter):
    async def get_paginated_resources(
        self, options: ResourceGraphExporterOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        query = format_query(options.query)
        logger.info(
            f"Exporting graph resources for {len(options.subscriptions)} subscriptions with query: {query}"
        )
        tasks = []
        for current_index in range(
            0, len(options.subscriptions), _SUBCRIPTION_BATCH_SIZE
        ):
            request = AzureRequest(
                endpoint="providers/Microsoft.ResourceGraph/resources",
                json_body={
                    "query": query,
                    "subscriptions": options.subscriptions[
                        current_index : current_index + _SUBCRIPTION_BATCH_SIZE
                    ],
                },
                method="POST",
            )

            tasks.append(self.client.make_paginated_request(request))
            if len(tasks) >= _MAX_CONCURRENT_REQUESTS:
                async for results in stream_async_iterators_tasks(*tasks):
                    logger.info(
                        f"Received batch of {len(results)} results from resource graph"
                    )
                    yield results
                    tasks.clear()
        if tasks:
            async for results in stream_async_iterators_tasks(*tasks):
                logger.info(
                    f"Received batch of {len(results)} results from resource graph"
                )
                yield results
