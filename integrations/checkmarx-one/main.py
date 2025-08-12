from typing import cast
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from checkmarx_one.exporter_factory import (
    create_project_exporter,
    create_scan_exporter,
    create_scan_result_exporter,
)
from checkmarx_one.core.options import (
    ListProjectOptions,
    ListScanOptions,
    ListScanResultOptions,
)
from integration import (
    CheckmarxOneScanResourcesConfig,
    CheckmarxOneScanResultResourcesConfig,
)
from checkmarx_one.utils import ObjectKind


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

    project_exporter = create_project_exporter()
    options = ListProjectOptions()

    async for projects_batch in project_exporter.get_paginated_resources(options):
        logger.debug(f"Received batch with {len(projects_batch)} projects")
        yield projects_batch


@ocean.on_resync(ObjectKind.SCAN)
async def on_scan_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync scans from Checkmarx One."""
    logger.info(f"Starting resync for kind: {kind}")

    scan_exporter = create_scan_exporter()

    config = cast(CheckmarxOneScanResourcesConfig, event.resource_config)
    selector = config.selector

    logger.info(selector)
    options = ListScanOptions(project_ids=selector.project_ids)

    async for scans_batch in scan_exporter.get_paginated_resources(options):
        logger.debug(f"Received batch with {len(scans_batch)} scans")
        yield scans_batch


@ocean.on_resync(ObjectKind.SCAN_RESULT)
async def on_scan_result_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync scan results from Checkmarx One."""
    logger.info(f"Starting resync for kind: {kind}")

    scan_exporter = create_scan_exporter()
    scan_result_exporter = create_scan_result_exporter()
    selector = cast(
        CheckmarxOneScanResultResourcesConfig, event.resource_config
    ).selector
    options = ListScanResultOptions(
        scan_id="",
        severity=selector.severity,
        state=selector.state,
        status=selector.status,
        exclude_result_types=selector.exclude_result_types,
    )

    scan_options = ListScanOptions()

    async for scan_data_list in scan_exporter.get_paginated_resources(scan_options):
        for scan_data in scan_data_list:
            options.update({"scan_id": scan_data["id"]})
            async for results_batch in scan_result_exporter.get_paginated_resources(
                options
            ):
                yield results_batch
