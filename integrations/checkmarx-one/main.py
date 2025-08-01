from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from checkmarx_one.exporter_factory import create_project_exporter, create_scan_exporter
from checkmarx_one.core.options import ListProjectOptions, ListScanOptions
from utils import ObjectKind


@ocean.on_start()
async def on_start() -> None:
    """Initialize the Checkmarx One integration."""
    logger.info("Starting Checkmarx One integration")
    try:
        logger.info("Checkmarx One integration initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Checkmarx One integration: {str(e)}")
        raise


@ocean.on_resync(ObjectKind.PROJECT)
async def on_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync projects from Checkmarx One."""
    logger.info(f"Starting resync for kind: {kind}")

    try:
        project_exporter = create_project_exporter()
        options = ListProjectOptions()

        async for projects_batch in project_exporter.get_projects(options):
            logger.debug(f"Received batch with {len(projects_batch)} projects")
            yield projects_batch

    except Exception as e:
        logger.error(f"Error during project resync: {str(e)}")
        raise


@ocean.on_resync(ObjectKind.SCAN)
async def on_scan_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync scans from Checkmarx One."""
    logger.info(f"Starting resync for kind: {kind}")

    try:
        scan_exporter = create_scan_exporter()
        options = ListScanOptions()

        async for scans_batch in scan_exporter.get_scans(options):
            logger.debug(f"Received batch with {len(scans_batch)} scans")
            yield scans_batch

    except Exception as e:
        logger.error(f"Error during scan resync: {str(e)}")
        raise
