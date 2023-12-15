from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from client import ServicenowClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


@ocean.on_resync()
async def on_resources_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Servicenow resource: {kind}")
    servicenow_client = ServicenowClient(
        ocean.integration_config["servicenow_instance"],
        ocean.integration_config["servicenow_username"],
        ocean.integration_config["servicenow_password"]
    )

    async for records in servicenow_client.get_paginated_resource():
        logger.warning(f"Received records batch with {len(records)} {kind}")
        yield records

@ocean.on_start()
async def on_start() -> None:
    print("Starting Servicenow integration")
