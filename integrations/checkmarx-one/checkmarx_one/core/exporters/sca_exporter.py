from typing import Any
from checkmarx_one.core.exporters.scan_result_exporter import (
    CheckmarxScanResultExporter,
)
from checkmarx_one.core.options import SingleScanResultOptions, ListScanResultOptions
from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE


class CheckmarxScaResultExporter(CheckmarxScanResultExporter):

    async def get_resource(self, options: SingleScanResultOptions) -> RAW_ITEM:
        """Get SCA scan result from Checkmarx One."""
        result = await self._get_resource(options)
        return self._enrich_scan_result_with_scan_id(result, options["scan_id"])

    async def get_paginated_resources(
        self, options: ListScanResultOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get SCA scan results from Checkmarx One."""
        async for batch in self._get_paginated_resources(options):
            batch = [
                self._enrich_scan_result_with_scan_id(
                    result,
                    options["scan_id"],
                )
                for result in batch
                if result["type"] == options["type"]
            ]
            yield batch
