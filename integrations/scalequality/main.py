from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import ScaleQualityClient
from integration import ObjectKind


def init_client() -> ScaleQualityClient:
    return ScaleQualityClient(
        base_url=ocean.integration_config["scale_quality_api_url"],
        api_key=ocean.integration_config["scale_quality_api_key"],
    )


@ocean.on_resync(ObjectKind.ENTITY)
async def on_resync_entities(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    async for entities in client.get_entities():
        logger.info(f"Resynced {len(entities)} ScaleQuality entities")
        yield entities


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting ScaleQuality integration")
