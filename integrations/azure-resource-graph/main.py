from enum import StrEnum
from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.exporters.resource_containers import ResourceContainersExporter
from azure_integration.exporters.resources import ResourcesExporter
from azure_integration.factory import init_client_and_sub_manager
from azure_integration.models import (
    ResourceContainerExporterOptions,
    ResourceExporterOptions,
)
from integration import AzureResourceConfig, AzureResourceContainerConfig


class Kind(StrEnum):
    RESOURCE_CONTAINER = "resourceContainer"
    RESOURCE = "resource"


@ocean.on_resync(Kind.RESOURCE_CONTAINER)
async def on_resync_resource_container(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Starting Azure to Port {kind} sync")
    selectors = cast(AzureResourceContainerConfig, event.resource_config).selector
    client, subscription_manager = init_client_and_sub_manager()
    async with client as client, subscription_manager as sub_manager:
        exporter_options = ResourceContainerExporterOptions(tag_filter=selectors.tags)
        exporter = ResourceContainersExporter(client, sub_manager)
        async for resources in exporter.get_paginated_resources(exporter_options):
            yield resources


@ocean.on_resync(Kind.RESOURCE)
async def on_resync_resource(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Starting Azure to Port {kind} sync")
    selectors = cast(AzureResourceConfig, event.resource_config).selector
    client, subscription_manager = init_client_and_sub_manager()
    async with client as client, subscription_manager as sub_manager:
        exporter_options = ResourceExporterOptions(
            resource_types=selectors.resource_types,
            tag_filter=selectors.resource_group_tags,
        )
        exporter = ResourcesExporter(client, sub_manager)
        async for resources in exporter.get_paginated_resources(exporter_options):
            yield resources
