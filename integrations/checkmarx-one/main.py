from typing import cast
from loguru import logger
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from checkmarx_one.exporter_factory import (
    create_project_exporter,
    create_sast_exporter,
    create_scan_exporter,
    create_api_sec_exporter,
    create_kics_exporter,
    create_scan_result_exporter,
    create_dast_scan_environment_exporter,
    create_dast_scan_exporter,
)
from checkmarx_one.core.options import (
    ListDastScanOptions,
    ListProjectOptions,
    ListSastOptions,
    ListScanOptions,
    ListApiSecOptions,
    ListKicsOptions,
    ListScanResultOptions,
)
from integration import (
    CheckmarxOneDastScanResultResourcesConfig,
    CheckmarxOneSastResourcesConfig,
    CheckmarxOneScanResourcesConfig,
    CheckmarxOneKicsResourcesConfig,
    CheckmarxOneScanResultResourcesConfig,
    CheckmarxOneApiSecResourcesConfig,
    CheckmarxOneDastScanResourcesConfig,
)
from checkmarx_one.utils import ObjectKind, ScanResultObjectKind
from checkmarx_one.webhook.webhook_processors.scan_webhook_processor import (
    ScanWebhookProcessor,
)
from checkmarx_one.webhook.webhook_processors.api_security_webhook_processor import (
    ApiSecurityWebhookProcessor,
)
from checkmarx_one.webhook.webhook_processors.sca_scan_result_webhook_processor import (
    ScaScanResultWebhookProcessor,
)
from checkmarx_one.webhook.webhook_processors.containers_scan_result_webhook_processor import (
    ContainersScanResultWebhookProcessor,
)
from checkmarx_one.webhook.webhook_processors.kics_scan_result_webhook_processor import (
    KicsScanResultWebhookProcessor,
)
from checkmarx_one.webhook.webhook_processors.sast_scan_result_webhook_processor import (
    SastScanResultWebhookProcessor,
)
from checkmarx_one.webhook.webhook_processors.project_webhook_processor import (
    ProjectWebhookProcessor,
)
from fetcher import fetch_dast_scan_results_for_environment

# Webhook endpoint constant
WEBHOOK_ENDPOINT = "/webhook"


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

    options = ListScanOptions(
        project_names=selector.project_names,
        branches=selector.branches,
        statuses=selector.statuses,
        from_date=selector.from_date,
    )

    async for scans_batch in scan_exporter.get_paginated_resources(options):
        logger.debug(f"Received batch with {len(scans_batch)} scans")
        yield scans_batch


@ocean.on_resync(ObjectKind.API_SEC)
async def on_api_sec_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync API security from Checkmarx One."""
    logger.info(f"Starting resync for kind: {kind}")

    scan_exporter = create_scan_exporter()
    api_sec_exporter = create_api_sec_exporter()

    config = cast(CheckmarxOneApiSecResourcesConfig, event.resource_config)
    selector = config.selector

    scan_options = ListScanOptions(
        project_names=selector.scan_filter.project_names,
        branches=selector.scan_filter.branches,
        statuses=selector.scan_filter.statuses,
        from_date=selector.scan_filter.from_date,
    )

    async for scan_data_list in scan_exporter.get_paginated_resources(scan_options):
        for scan_data in scan_data_list:
            options = ListApiSecOptions(
                scan_id=scan_data["id"],
            )
            async for results_batch in api_sec_exporter.get_paginated_resources(
                options
            ):
                logger.info(
                    f"Received batch with {len(results_batch)} API security risks for scan {scan_data['id']}"
                )
                yield results_batch


@ocean.on_resync(ObjectKind.SAST)
async def on_sast_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync SAST from Checkmarx One."""
    logger.info(f"Starting resync for kind: {kind}")

    sast_exporter = create_sast_exporter()
    scan_exporter = create_scan_exporter()

    config = cast(CheckmarxOneSastResourcesConfig, event.resource_config)
    selector = config.selector

    scan_options = ListScanOptions(
        project_names=selector.scan_filter.project_names,
        branches=selector.scan_filter.branches,
        statuses=selector.scan_filter.statuses,
        from_date=selector.scan_filter.from_date,
    )
    async for scan_data_list in scan_exporter.get_paginated_resources(scan_options):
        for scan_data in scan_data_list:
            options = ListSastOptions(
                scan_id=scan_data["id"],
                severity=selector.severity,
                status=selector.status,
                state=selector.state,
                category=selector.category,
                language=selector.language,
                group=selector.group,
                include_nodes=selector.include_nodes,
                result_id=selector.result_id,
                compliance=selector.compliance,
            )
            async for results_batch in sast_exporter.get_paginated_resources(options):
                logger.info(
                    f"Received batch with {len(results_batch)} SAST for scan {scan_data['id']}"
                )
                yield results_batch


@ocean.on_resync(ObjectKind.KICS)
async def on_kics_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync KICS (IaC Security) results from Checkmarx One."""
    logger.info(f"Starting resync for kind: {kind}")

    scan_exporter = create_scan_exporter()
    kics_exporter = create_kics_exporter()

    # Get selector options from config
    config = cast(CheckmarxOneKicsResourcesConfig, event.resource_config)
    selector = config.selector

    scan_options = ListScanOptions(
        project_names=selector.scan_filter.project_names,
        branches=selector.scan_filter.branches,
        statuses=selector.scan_filter.statuses,
        from_date=selector.scan_filter.from_date,
    )
    logger.warning(f"Scan options: {scan_options}")

    async for scan_data_list in scan_exporter.get_paginated_resources(scan_options):
        for scan_data in scan_data_list:
            options = ListKicsOptions(
                scan_id=scan_data["id"],
                severity=selector.severity,
                status=selector.status,
            )
            async for results_batch in kics_exporter.get_paginated_resources(options):
                logger.info(
                    f"Received batch with {len(results_batch)} KICS results for scan {scan_data['id']}"
                )
                yield results_batch


@ocean.on_resync()
async def on_scan_result_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync scan results from Checkmarx One."""
    if kind not in ScanResultObjectKind:
        if kind in ObjectKind:
            logger.debug(f"Kind {kind} has a special handling. Skipping...")
        else:
            logger.info(f"Kind {kind} not supported. Skipping...")
        return

    logger.info(f"Starting resync for kind: {kind}")

    scan_exporter = create_scan_exporter()
    scan_result_exporter = create_scan_result_exporter()
    selector = cast(
        CheckmarxOneScanResultResourcesConfig, event.resource_config
    ).selector

    scan_options = ListScanOptions(
        project_names=selector.scan_filter.project_names,
        branches=selector.scan_filter.branches,
        statuses=selector.scan_filter.statuses,
        from_date=selector.scan_filter.from_date,
    )

    async for scan_data_list in scan_exporter.get_paginated_resources(scan_options):
        for scan_data in scan_data_list:
            options = ListScanResultOptions(
                scan_id=scan_data["id"],
                type=kind,
                severity=selector.severity,
                state=selector.state,
                status=selector.status,
                exclude_result_types=selector.exclude_result_types,
            )
            async for results_batch in scan_result_exporter.get_paginated_resources(
                options
            ):
                logger.info(
                    f"Fetched {len(results_batch)} scan results {kind} for scan {scan_data['id']}"
                )
                yield results_batch


@ocean.on_resync(ObjectKind.DAST_SCAN_ENVIRONMENT)
async def on_dast_scan_environment_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync DAST scan environments from Checkmarx One."""

    exporter = create_dast_scan_environment_exporter()

    async for dast_scan_environments in exporter.get_paginated_resources():
        logger.debug(
            f"Received batch with {len(dast_scan_environments)} DAST scan environments"
        )
        yield dast_scan_environments


@ocean.on_resync(ObjectKind.DAST_SCAN)
async def on_dast_scan_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync DAST scans from Checkmarx One."""

    dast_scan_environment_exporter = create_dast_scan_environment_exporter()
    dast_scan_exporter = create_dast_scan_exporter()

    selector = cast(CheckmarxOneDastScanResourcesConfig, event.resource_config).selector

    async for (
        dast_scans_environments_batch
    ) in dast_scan_environment_exporter.get_paginated_resources():
        tasks = [
            dast_scan_exporter.get_paginated_resources(
                ListDastScanOptions(
                    environment_id=dast_scan_environment["environmentId"],
                    scan_type=selector.scan_type,
                    updated_from_date=selector.updated_from_date,
                    max_results=selector.max_results,
                )
            )
            for dast_scan_environment in dast_scans_environments_batch
        ]
        async for dast_scans_batch in stream_async_iterators_tasks(*tasks):
            yield dast_scans_batch


@ocean.on_resync(ObjectKind.DAST_SCAN_RESULT)
async def on_dast_scan_result_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync DAST scan results from Checkmarx One."""

    dast_scan_environment_exporter = create_dast_scan_environment_exporter()
    selector = cast(
        CheckmarxOneDastScanResultResourcesConfig, event.resource_config
    ).selector

    async for env_batch in dast_scan_environment_exporter.get_paginated_resources():
        results = []
        for env in env_batch:
            results.extend(await fetch_dast_scan_results_for_environment(env, selector))
        yield results


# Register webhook processors for Checkmarx One events
ocean.add_webhook_processor(WEBHOOK_ENDPOINT, ScanWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_ENDPOINT, ApiSecurityWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_ENDPOINT, ScaScanResultWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_ENDPOINT, ContainersScanResultWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_ENDPOINT, KicsScanResultWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_ENDPOINT, SastScanResultWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_ENDPOINT, ProjectWebhookProcessor)
