from loguru import logger

from models import KomoObjectKind
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import KomodorClient


def init_client() -> KomodorClient:
    return KomodorClient(
        api_key=ocean.integration_config["komodor_api_key"],
        api_url=ocean.integration_config["komodor_base_url"],
    )


@ocean.on_resync(KomoObjectKind.SERVICE)
async def resync_services(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    async for service in client.get_all_services():
        logger.info(f"Got {len(service)} services from komodor api")
        yield service


@ocean.on_resync(KomoObjectKind.HEALTH_MONITOR)
async def resync_health_monitor(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    async for healh_monitoring in client.get_health_monitor():
        logger.info(f"Got {len(healh_monitoring)} health monitoring from komodor api")
        yield healh_monitoring


# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting komodor integration")
