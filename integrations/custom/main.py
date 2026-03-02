from typing import cast

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from custom.clients.initialize_client import get_client
from custom.core.exporters.resource_exporter import HttpResourceExporter
from custom.core.options import FetchResourceOptions
from custom.helpers.endpoint_cache import (
    initialize_endpoint_cache,
    clear_endpoint_cache,
)
from integration import HttpServerResourceConfig


@ocean.on_resync_start()
async def on_resync_start() -> None:
    app_config = event.port_app_config
    resources = [cast(HttpServerResourceConfig, r) for r in app_config.resources]
    initialize_endpoint_cache(resources)


@ocean.on_resync_complete()
async def on_resync_complete() -> None:
    clear_endpoint_cache()


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Starting resync for kind (endpoint): {kind}")

    client = get_client()
    exporter = HttpResourceExporter(client)

    resource_config = cast(HttpServerResourceConfig, event.resource_config)

    options: FetchResourceOptions = {
        "kind": kind,
        "selector": resource_config.selector,
    }

    async for batch in exporter.get_paginated_resources(options):
        yield batch
