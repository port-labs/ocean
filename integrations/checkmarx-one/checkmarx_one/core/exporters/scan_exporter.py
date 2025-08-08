from collections.abc import AsyncGenerator
from typing import Any
from loguru import logger

from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from port_ocean.utils.cache import cache_iterator_result
from typing import Dict
from checkmarx_one.core.options import SingleScanOptions, ListScanOptions


class CheckmarxScanExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One scans."""

    async def get_resource(
        self,
        options: SingleScanOptions,
    ) -> Dict[str, Any]:
        """Get a specific scan by ID."""
        response = await self.client.send_api_request(f"/scans/{options['scan_id']}")
        logger.info(f"Fetched scan with ID: {options['scan_id']}")
        return response

    @cache_iterator_result()
    async def get_paginated_resources(
        self,
        options: ListScanOptions,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
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
        project_ids = options.get("project_ids")
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
