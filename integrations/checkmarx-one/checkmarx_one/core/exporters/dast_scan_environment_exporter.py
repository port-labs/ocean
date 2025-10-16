from typing import Any
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from port_ocean.utils.cache import cache_iterator_result


class CheckmarxDastScanEnvironmentExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One DAST scan environments."""

    async def get_resource(self, options: Any) -> Any:
        raise NotImplementedError(
            "Fetching single DAST scan environment is not supported"
        )

    @cache_iterator_result()
    async def get_paginated_resources(
        self,
        options: None = None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for (
            dast_scan_environments
        ) in self.client.send_paginated_request_offset_based(
            "/dast/scans/environments", "environments"
        ):
            logger.info(
                f"Fetched batch of {len(dast_scan_environments)} DAST scan environments"
            )
            yield dast_scan_environments
