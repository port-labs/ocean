from typing import cast
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from checkmarx_one.exporter_factory import (
    create_project_exporter,
    create_scan_exporter,
    create_scan_result_exporter,
    create_api_sec_exporter,
)
from checkmarx_one.core.options import (
    ListProjectOptions,
    ListScanOptions,
    ListScanResultOptions,
    ListApiSecOptions,
)
from integration import (
    CheckmarxOneScanResourcesConfig,
    CheckmarxOneApiSecResourcesConfig,
    ScanResultConfigType,
)
from checkmarx_one.utils import ObjectKind, ALLOWED_KINDS_FOR_SCAN_RESULT


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


@ocean.on_resync()
async def on_scan_result_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync scan results from Checkmarx One."""
    logger.info(f"Starting resync for kind: {kind}")

    if kind not in ALLOWED_KINDS_FOR_SCAN_RESULT:
        logger.debug(f"Skipping resync for kind not for scan results: {kind}")
        return
    if kind == "containersec":
        kind = "containers"

    scan_exporter = create_scan_exporter()
    scan_result_exporter = create_scan_result_exporter()
    selector = cast(ScanResultConfigType, event.resource_config).selector
    options = ListScanResultOptions(
        scan_id="",
        kind=kind,
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
                logger.info(
                    f"Received batch with {len(results_batch)} scan results for kind: {kind}"
                )
                yield results_batch


@ocean.on_resync(ObjectKind.API_SEC)
async def on_api_sec_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync API security from Checkmarx One."""
    logger.info(f"Starting resync for kind: {kind}")

    scan_exporter = create_scan_exporter()
    api_sec_exporter = create_api_sec_exporter()
    config = cast(CheckmarxOneApiSecResourcesConfig, event.resource_config)
    selector = config.selector

    scan_options = ListScanOptions()

    async for scan_data_list in scan_exporter.get_paginated_resources(scan_options):
        for scan_data in scan_data_list:
            options = ListApiSecOptions(
                scan_id=scan_data["id"],
                filtering=selector.filtering,
                searching=selector.searching,
                sorting=selector.sorting,
            )
            async for results_batch in api_sec_exporter.get_paginated_resources(
                options
            ):
                logger.info(
                    f"Received batch with {len(results_batch)} API security risks for scan {scan_data['id']}"
                )
                yield results_batch
