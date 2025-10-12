from typing import Any, Dict
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from port_ocean.utils.cache import cache_iterator_result
from checkmarx_one.core.options import ListDastScanOptions


class CheckmarxDastScanExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One DAST scans."""

    def _build_params(self, options: ListDastScanOptions) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "environmentId": options["environment_id"],
            "sort": "updatetime:desc",
        }

        if scan_type := options.get("scan_type"):
            params["match.scantype"] = scan_type

        return params

    def _enrich_dast_scan_with_environment_id(
        self, dast_scan: Dict[str, Any], environment_id: str
    ) -> dict[str, Any]:
        """Enrich DAST scan with environment ID."""
        dast_scan["__environment_id"] = environment_id
        return dast_scan

    async def get_resource(self, options: Any) -> Any:
        raise NotImplementedError("Fetching single DAST scan is not supported")

    async def get_paginated_resources(
        self,
        options: ListDastScanOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        environment_id = options["environment_id"]
        updated_from_date = options["updated_from_date"]
        max_results = options["max_results"]

        params = self._build_params(options)
        total_yielded = 0

        async for results in self.client.send_paginated_request_offset_based(
            "/dast/scans/scans", "scans", params
        ):
            batch = [r for r in results if r["updateTime"] >= updated_from_date]
            batch_count = len(batch)
            if batch_count == 0:
                continue

            remaining = max_results - total_yielded
            if remaining <= 0:
                break

            if batch_count > remaining:
                batch = batch[:remaining]

            logger.info(f"Fetched batch of {len(batch)} DAST scans")

            yield [
                self._enrich_dast_scan_with_environment_id(result, environment_id)
                for result in batch
            ]

            total_yielded += len(batch)

            if total_yielded >= max_results:
                logger.info(f"Reached max_results={max_results}, stopping early.")
                break