from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.helpers.retry import register_retry_config_callback

from factory_ai.clients.client_factory import ClientFactory
from factory_ai.clients.factory_client import create_factory_retry_config
from factory_ai.exporter_factory import get_exporter_metadata
from factory_ai.kinds import ObjectKind

register_retry_config_callback(create_factory_retry_config)


@ocean.on_resync()
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    metadata = get_exporter_metadata(ObjectKind(kind))
    exporter = metadata.exporter(ClientFactory.get_client())
    async for batch in exporter.get_paginated_resources(metadata.list_options_model()):
        if batch:
            yield batch


@ocean.on_start()
async def on_start() -> None:
    # Factory Public API has no outbound webhooks, so there is nothing to
    # register for live events.
    logger.info("Starting factory-ai integration")
