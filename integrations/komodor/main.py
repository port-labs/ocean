from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import KomodorClient


def init_client() -> KomodorClient:
    return KomodorClient(api_key=ocean.integration_config["komodor_api_key"],
                         api_url=ocean.integration_config["komodor_base_url"])

@ocean.on_resync("komodorService")
async def resync_services(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    async for service in client.get_all_services():
        logger.info(f"Got {len(service)} services from komodor api")
        yield service


@ocean.on_resync("komodorRiskViolations")
async def resync_risks(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    async for risks in client.get_risks():
        logger.info(f"Got {len(risks)} risks from komodor api.")
        yield risks


@ocean.on_resync("komodorIssues")
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    async for issues in client.get_issues():
        logger.info(f"Got {len(issues)} issues from komodor api.")
        yield issues


# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.warning("Starting komodor integration")
