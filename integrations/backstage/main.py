from enum import StrEnum

from client import BackstageClient
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    COMPONENT = "component"
    API = "api"
    GROUP = "group"
    USER = "user"
    SYSTEM = "system"
    DOMAIN = "domain"
    RESOURCE = "resource"


def init_client() -> BackstageClient:
    return BackstageClient(
        backstage_host=ocean.integration_config["backstage_url"],
        backstage_token=ocean.integration_config["backstage_token"],
    )


@ocean.on_resync()
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    async for entities in client.get_all_entities_by_kind(kind):
        yield entities


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting backstage integration")
