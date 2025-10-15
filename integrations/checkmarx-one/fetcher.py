import asyncio
from checkmarx_one.exporter_factory import (
    create_dast_scan_exporter,
    create_dast_scan_result_exporter,
)
from checkmarx_one.core.options import ListDastScanOptions, ListDastScanResultOptions
from loguru import logger
from typing import TYPE_CHECKING, Dict, Any, cast

if TYPE_CHECKING:
    from integration import CheckmarxOneDastScanResultSelector
    from checkmarx_one.core.exporters.dast_scan_result_exporter import (
        CheckmarxDastScanResultExporter,
    )


async def fetch_dast_scan_results(
    dast_scan_id: str,
    selector: "CheckmarxOneDastScanResultSelector",
    dast_scan_result_exporter: "CheckmarxDastScanResultExporter",
) -> list[Dict[str, Any]]:
    """Fetch all paginated DAST results for a single scan."""
    options = ListDastScanResultOptions(
        dast_scan_id=dast_scan_id,
        severity=selector.filter.severity,
        status=selector.filter.status,
        state=selector.filter.state,
    )

    all_results: list[Dict[str, Any]] = []
    async for results_batch in dast_scan_result_exporter.get_paginated_resources(
        options
    ):
        all_results.extend(results_batch)

    logger.info(f"Fetched {len(all_results)} DAST results for scan {dast_scan_id}")
    return all_results


async def fetch_dast_scan_results_for_environment(
    dast_scan_environment: Dict[str, Any],
    selector: "CheckmarxOneDastScanResultSelector",
) -> list[Dict[str, Any]]:
    """Fetch all scans and their results for a given DAST environment."""

    dast_scan_exporter = create_dast_scan_exporter()
    dast_scan_result_exporter = create_dast_scan_result_exporter()

    env_id = dast_scan_environment["environmentId"]

    dast_scan_options = ListDastScanOptions(
        environment_id=env_id,
        scan_type=selector.dast_scan_filter.scan_type,
        updated_from_date=selector.dast_scan_filter.updated_from_date,
        max_results=selector.dast_scan_filter.max_results,
    )

    tasks = []
    async for dast_scans_batch in dast_scan_exporter.get_paginated_resources(
        dast_scan_options
    ):
        for dast_scan in dast_scans_batch:
            scan_id = dast_scan["scanId"]
            tasks.append(
                asyncio.create_task(
                    fetch_dast_scan_results(
                        scan_id, selector, dast_scan_result_exporter
                    )
                )
            )

    if not tasks:
        logger.info(f"No scans found for environment {env_id}")
        return []

    results_batches = await asyncio.gather(*tasks, return_exceptions=True)

    merged: list[Dict[str, Any]] = []
    for result in results_batches:
        if isinstance(result, Exception):
            logger.warning(f"Error fetching DAST scan results: {result}")
            continue
        merged.extend(cast(list[Dict[str, Any]], result))

    logger.info(f"Environment {env_id}: {len(merged)} total results")
    return merged
