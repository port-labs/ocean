from enum import StrEnum
from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.exporters.resource_graph import ResourceGraphExporter
from azure_integration.exporters.subscription import SubscriptionExporter
from azure_integration.factory import create_azure_client
from azure_integration.options import (
    ResourceGraphExporterOptions,
)
from integration import (
    AzureResourceGraphConfig,
)


class Kind(StrEnum):
    GRAPH_RESOURCE = "graphResource"
    SUBSCRIPTION = "subscription"


@ocean.on_resync(Kind.SUBSCRIPTION)
async def on_resync_subscription(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Starting Azure to Port {kind} sync")
    azure_client = create_azure_client()
    subscription_exporter = SubscriptionExporter(azure_client)
    async for subscriptions in subscription_exporter.get_paginated_resources():
        yield subscriptions


@ocean.on_resync(Kind.GRAPH_RESOURCE)
async def on_resync_resource_graph(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Starting Azure to Port {kind} sync")
    selectors = cast(AzureResourceGraphConfig, event.resource_config).selector
    azure_client = create_azure_client()
    resource_graph_exporter = ResourceGraphExporter(azure_client)
    subscription_exporter = SubscriptionExporter(azure_client)
    async for subscriptions in subscription_exporter.get_paginated_resources():
        subscription_ids = [
            subscription["subscriptionId"] for subscription in subscriptions
        ]
        exporter_options = ResourceGraphExporterOptions(
            query=selectors.graph_query, subscriptions=subscription_ids
        )
        async for results in resource_graph_exporter.get_paginated_resources(
            exporter_options
        ):
            yield results


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting azure multi subscription integration")
