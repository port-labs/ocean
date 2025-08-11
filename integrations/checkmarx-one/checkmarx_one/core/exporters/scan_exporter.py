from typing import Any, Optional, AsyncGenerator, Mapping
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from port_ocean.utils.cache import cache_iterator_result


class CheckmarxScanExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One scans."""

    async def get_resource(
        self,
        options: Optional[Mapping[str, Any]],
    ) -> RAW_ITEM:
        """Get a specific scan by ID."""
        assert options is not None and "scan_id" in options
        response = await self.client.send_api_request(f"/scans/{options['scan_id']}")
        logger.info(f"Fetched scan with ID: {options['scan_id']}")
        return response

    @cache_iterator_result()
    def get_paginated_resources(
        self,
        options: Optional[Mapping[str, Any]],
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
        params: dict[str, Any] = {}
        project_ids: list[str] = (options or {}).get("project_ids", []) or []
        limit = (options or {}).get("limit")
        offset = (options or {}).get("offset")

        if project_ids and len(project_ids) > 0:
            params["project-ids"] = ",".join(project_ids)
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        async def _gen() -> AsyncGenerator[list[dict[str, Any]], None]:
            async for scans in self.client.send_paginated_request(
                "/scans", "scans", params
            ):
                logger.info(f"Fetched batch of {len(scans)} scans")
                yield scans

        return _gen()
