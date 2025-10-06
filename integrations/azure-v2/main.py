from enum import StrEnum
from typing import Type

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.client import AzureClient
from azure_integration.exporters.base import BaseExporter
from azure_integration.exporters.resources import (
    ResourceContainersExporter,
    ResourcesExporter,
)


class Kind(StrEnum):
    RESOURCE_CONTAINER = "resourceContainer"
    RESOURCE = "resource"


EXPORTER_MAP: dict[str, Type[BaseExporter]] = {
    Kind.RESOURCE_CONTAINER: ResourceContainersExporter,
    Kind.RESOURCE: ResourcesExporter,
}


@ocean.on_resync()
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Starting Azure to Port {kind} sync")

    if exporter_class := EXPORTER_MAP.get(kind):
        async with AzureClient() as azure_client:
            exporter = exporter_class(azure_client)
            async for resources in exporter.export():
                yield resources
    else:
        logger.warning(f"No exporter found for kind: {kind}")


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting azure multi subscription integration")
