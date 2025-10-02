from typing import Generator, cast
from enum import StrEnum

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from clients.azure_client import AzureClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from integration import AzureResourceConfig
from services.resource_containers import ResourceContainers
from services.resources import Resources
from utils import turn_sequence_to_chunks

from loguru import logger
from azure.mgmt.subscription.models._models_py3 import Subscription


class Kind(StrEnum):
    RESOURCE_CONTAINER = "resourceContainer"
    RESOURCE = "resource"


# Required
# Listen to the resync event of all the kinds specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
@ocean.on_resync(Kind.RESOURCE_CONTAINER)
async def on_resync_resource_container(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Starting Azure to Port resource container sync")
    subscription_batch_size = int(ocean.integration_config["subscription_batch_size"])

    async with (AzureClient() as azure_client,):
        all_subscriptions = await azure_client.get_all_subscriptions()
        logger.info(f"Discovered {len(all_subscriptions)} subscriptions")

        if not all_subscriptions:
            logger.error("No subscriptions found in Azure, exiting")
            return

        subscriptions_batches: Generator[list[Subscription], None, None] = (
            turn_sequence_to_chunks(
                all_subscriptions,
                subscription_batch_size,
            )
        )

        resource_containers_syncer = ResourceContainers(azure_client)

        for subscriptions in subscriptions_batches:
            logger.info("Running full resource container sync")
            async for resource_containers in resource_containers_syncer.sync_full(
                [str(s.subscription_id) for s in subscriptions],
            ):
                yield resource_containers
            logger.info("Completed full resource container sync")


@ocean.on_resync(Kind.RESOURCE)
async def on_resync_resource(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Starting Azure to Port resource sync")
    subscription_batch_size = int(ocean.integration_config["subscription_batch_size"])
    resource_confg = cast(AzureResourceConfig, event.resource_config)
    resource_types = resource_confg.selector.resource_types

    async with (AzureClient() as azure_client,):
        all_subscriptions = await azure_client.get_all_subscriptions()
        logger.info(f"Discovered {len(all_subscriptions)} subscriptions")

        if not all_subscriptions:
            logger.error("No subscriptions found in Azure, exiting")
            return

        subscriptions_batches: Generator[list[Subscription], None, None] = (
            turn_sequence_to_chunks(all_subscriptions, subscription_batch_size)
        )

        resources_syncer = Resources(azure_client)

        for subscriptions in subscriptions_batches:
            logger.info("Running full resource sync")
            async for resources in resources_syncer.sync_full(
                [str(s.subscription_id) for s in subscriptions],
                resource_types=resource_types,
            ):
                yield resources


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting azure multi subscription integration")
