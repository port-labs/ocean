from enum import StrEnum

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.client import AzureClient
from azure_integration.core.exporters.resources import (
    ResourceContainersExporter,
    ResourcesExporter,
)


class Kind(StrEnum):
    RESOURCE_CONTAINER = "resourceContainer"
    RESOURCE = "resource"


@ocean.on_resync(Kind.RESOURCE_CONTAINER)
async def on_resync_resource_container(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Starting Azure to Port {kind} sync")
    async with AzureClient() as azure_client:
        exporter = ResourceContainersExporter(azure_client)
        async for resources in exporter.export():
            yield resources


@ocean.on_resync(Kind.RESOURCE)
async def on_resync_resource(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Starting Azure to Port {kind} sync")
    async with AzureClient() as azure_client:
        exporter = ResourcesExporter(azure_client)
        async for resources in exporter.export():
            yield resources


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting azure multi subscription integration")
