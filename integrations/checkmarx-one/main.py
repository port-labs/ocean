from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from initialize_client import init_client
from utils import ObjectKind

# Global client instance
checkmarx_client = None


@ocean.on_start()
async def on_start() -> None:
    """Initialize the Checkmarx One client when the integration starts."""
    global checkmarx_client
    logger.info("Starting Checkmarx One integration")

    try:
        checkmarx_client = init_client()
        logger.info("Checkmarx One client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Checkmarx One client: {str(e)}")
        raise


@ocean.on_resync(ObjectKind.PROJECT)
async def on_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync projects from Checkmarx One."""
    global checkmarx_client

    if not checkmarx_client:
        logger.error("Checkmarx client not initialized")
        return

    logger.info("Starting project resync")

    try:
        async for projects_batch in checkmarx_client.get_projects():
            logger.debug(f"Received batch with {len(projects_batch)} projects")
            yield projects_batch

    except Exception as e:
        logger.error(f"Error during project resync: {str(e)}")
        raise


@ocean.on_resync(ObjectKind.SCAN)
async def on_scan_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync scans from Checkmarx One."""
    global checkmarx_client

    if not checkmarx_client:
        logger.error("Checkmarx client not initialized")
        return

    logger.info("Starting scan resync")

    try:
        async for scans_batch in checkmarx_client.get_scans():
            logger.debug(f"Received batch with {len(scans_batch)} scans")
            yield scans_batch

    except Exception as e:
        logger.error(f"Error during scan resync: {str(e)}")
        raise
