from typing import Any
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from port_ocean.utils.cache import cache_iterator_result
from checkmarx_one.core.options import SingleScanOptions, ListScanOptions


class CheckmarxScanExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One scans."""

    async def get_resource(
        self,
        options: SingleScanOptions,
    ) -> RAW_ITEM:
        """Get a specific scan by ID."""
        response = await self.client.send_api_request(f"/scans/{options['scan_id']}")
        logger.info(f"Fetched scan with ID: {options['scan_id']}")
        return response

    @cache_iterator_result()
    async def get_paginated_resources(
        self,
        options: ListScanOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get scans from Checkmarx One.

        Args:
            project_id: Filter scans by project ID
            limit: Maximum number of scans per page
            offset: Starting offset for pagination

        Yields:
            Batches of scans
        """
        params: dict[str, Any] = self._get_params(options)
        async for scans in self.client.send_paginated_request(
            "/scans", "scans", params
        ):
            logger.info(f"Fetched batch of {len(scans)} scans")
            yield scans

    def _get_params(self, options: ListScanOptions) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if project_names := options.get("project_names"):
            params["project-names"] = project_names
        if branches := options.get("branches"):
            params["branches"] = branches
        if statuses := options.get("statuses"):
            params["statuses"] = statuses
        if from_date := options.get("from_date"):
            params["from-date"] = from_date
        return params
