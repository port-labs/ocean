from loguru import logger
from port_ocean.context.ocean import ocean


@ocean.on_start()
async def on_start() -> None:
    # Factory Public API has no outbound webhooks, so there is nothing to
    # register for live events.
    logger.info("Starting factory-ai integration")
