from itertools import batched

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from azure_integration.exporters.base import BaseExporter
from azure_integration.options import (
    ResourceGraphExporterOptions,
)
from azure_integration.helpers.http import format_query
from azure_integration.clients.base import AzureRequest
from port_ocean.context.ocean import ocean

# Due to a bug in the Azure API, when working in multiple batches and Azure contains a lot of resources
# per subscription, the results become inconsistent UNSELL order by clause is used. Do not change this value without validating the
# exact use-case of the customers using this integration
_DEFAULT_SUBSCRIPTION_BATCH_SIZE = 100
_MAX_CONCURRENT_REQUESTS = 10


def _get_subscription_batch_size() -> int:
    """Get subscription batch size from config at runtime when ocean context is available."""
    return ocean.integration_config.get(
        "azure_subscription_batch_size", _DEFAULT_SUBSCRIPTION_BATCH_SIZE
    )


class ResourceGraphExporter(BaseExporter):
    async def get_paginated_resources(
        self, options: ResourceGraphExporterOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        query = format_query(options.query)
        tasks = []
        subscription_batch_size = _get_subscription_batch_size()
        logger.info(f"Using subscription batch size: {subscription_batch_size}")
        for subscription_batch in batched(
            options.subscriptions, subscription_batch_size
        ):
            subscription_ids = [sub["subscriptionId"] for sub in subscription_batch]
            logger.info(
                f"Fetching graph resources from a batch of {len(subscription_ids)} subscriptions"
            )
            request = AzureRequest(
                endpoint="providers/Microsoft.ResourceGraph/resources",
                json_body={
                    "query": query,
                    "subscriptions": subscription_ids,
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
