from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import ListScanOptions, SingleScanOptions


class CheckmarxScanExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One scans."""

    async def get_resource[
        ExporterOptionsT: SingleScanOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        """Get a single scan by ID."""
        scan_id = options["scan_id"]
        scan = await self.client.get_scan_by_id(scan_id)
        logger.info(f"Fetched scan with ID: {scan_id}")
        return scan

    async def get_paginated_resources[
        ExporterOptionsT: ListScanOptions
    ](self, options: ExporterOptionsT | None = None) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all scans with pagination."""
        if options is None:
            options = {}

        project_id = options.get("project_id")
        limit = options.get("limit")
        offset = options.get("offset")

        async for scans_batch in self.client.get_scans(
            project_id=project_id, limit=limit, offset=offset
        ):
            logger.info(f"Fetched batch of {len(scans_batch)} scans")
            yield scans_batch
