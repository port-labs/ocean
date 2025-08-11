from typing import Any
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from port_ocean.utils.cache import cache_iterator_result
from checkmarx_one.core.options import SingleScanOptions, ListScanOptions


class CheckmarxScanExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One scans."""

    async def get_resource[
        SingleScanOptionsT: SingleScanOptions
    ](self, options: SingleScanOptionsT,) -> RAW_ITEM:
        """Get a specific scan by ID."""
        response = await self.client.send_api_request(f"/scans/{options['scan_id']}")
        logger.info(f"Fetched scan with ID: {options['scan_id']}")
        return response

    @cache_iterator_result()
    async def get_paginated_resources[
        ListScanOptionsT: ListScanOptions
    ](self, options: ListScanOptionsT,) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get scans from Checkmarx One.

        Args:
            project_id: Filter scans by project ID
            limit: Maximum number of scans per page
            offset: Starting offset for pagination

        Yields:
            Batches of scans
        """
        params: dict[str, Any] = {}
        project_ids: list[str] = options.get("project_ids", [])
        limit = options.get("limit")
        offset = options.get("offset")

        if project_ids and len(project_ids) > 0:
            params["project-ids"] = ",".join(project_ids)
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        async for scans in self.client.send_paginated_request(
            "/scans", "scans", params
        ):
            logger.info(f"Fetched batch of {len(scans)} scans")
            yield scans
