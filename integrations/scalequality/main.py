from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean

from client import ScaleQualityClient
from integration import ObjectKind


def init_client() -> ScaleQualityClient:
    return ScaleQualityClient(
        base_url=ocean.integration_config["scale_quality_api_url"],
        api_key=ocean.integration_config["scale_quality_api_key"],
    )


@ocean.on_resync(ObjectKind.ENTITY)
async def on_resync_entities(kind: str) -> list[dict[Any, Any]]:
    client = init_client()
    entities = await client.get_entities()
    logger.info(f"Resynced {len(entities)} ScaleQuality entities")
    return entities


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting ScaleQuality integration")
