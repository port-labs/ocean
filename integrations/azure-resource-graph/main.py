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
    SubscriptionExporterOptions,
)
from integration import (
    AzureResourceGraphConfig,
    AzureSubscriptionResourceConfig,
)
from azure_integration.factory import AzureClientType


class KindWithSpecialHandling(StrEnum):
    SUBSCRIPTION = "subscription"


@ocean.on_resync(KindWithSpecialHandling.SUBSCRIPTION)
async def on_resync_subscription(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Starting resync of {kind}")
    selectors = cast(AzureSubscriptionResourceConfig, event.resource_config).selector
    exporter_options = SubscriptionExporterOptions(
        api_version=selectors.api_params.version
    )
    azure_client = create_azure_client(AzureClientType.RESOURCE_MANAGER)
    subscription_exporter = SubscriptionExporter(azure_client)
    async for subscriptions in subscription_exporter.get_paginated_resources(
        exporter_options
    ):
        yield subscriptions


@ocean.on_resync()
async def on_resync_resource_graph(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    if kind in KindWithSpecialHandling:
        return

    logger.info(f"Starting resync of {kind} from resource graph")
    selectors = cast(AzureResourceGraphConfig, event.resource_config).selector
    azure_resource_graph_client = create_azure_client(AzureClientType.RESOURCE_GRAPH)
    azure_resource_manager_client = create_azure_client(
        AzureClientType.RESOURCE_MANAGER
    )
    resource_graph_exporter = ResourceGraphExporter(azure_resource_graph_client)
    subscription_exporter = SubscriptionExporter(azure_resource_manager_client)
    async for subscriptions in subscription_exporter.get_paginated_resources(
        SubscriptionExporterOptions(
            api_version=selectors.subscription.api_params.version
        )
    ):
        subscription_ids = [
            subscription["subscriptionId"] for subscription in subscriptions
        ]
        logger.info(
            f"Fetching {kind}`s for {len(subscription_ids)} subscriptions from resource graph"
        )
        exporter_options = ResourceGraphExporterOptions(
            api_version=selectors.api_params.version,
            query=selectors.graph_query,
            subscriptions=subscription_ids,
        )
        async for results in resource_graph_exporter.get_paginated_resources(
            exporter_options
        ):
            yield results


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting azure multi subscription integration")
