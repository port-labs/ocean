from typing import Any, Dict
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import ListDastScanResultOptions


class CheckmarxDastScanResultExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One DAST results per scan."""

    def _enrich_scan_result_with_dast_scan_id(
        self, dast_scan_result: Dict[str, Any], dast_scan_id: str
    ) -> dict[str, Any]:
        """Enrich scan result with scan ID."""
        dast_scan_result["__dast_scan_id"] = dast_scan_id
        return dast_scan_result

    async def get_resource(self, options: Any) -> Any:
        raise NotImplementedError("Fetching single DAST result is not supported")

    def _build_params(self, options: ListDastScanResultOptions) -> dict[str, Any]:
        """Build query parameters for DAST scan results API request."""
        params: dict[str, Any] = {}

        if severity := options.get("severity"):
            params["severity"] = severity
        if status := options.get("status"):
            params["status"] = status
        if state := options.get("state"):
            params["state"] = state

        return params

    async def get_paginated_resources(
        self,
        options: ListDastScanResultOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params: dict[str, Any] = self._build_params(options)
        dast_scan_id = options["dast_scan_id"]
        endpoint = f"/dast/mfe-results/results/{dast_scan_id}"
        async for results in self.client.send_paginated_request_page_based(
            endpoint, "results", params
        ):
            logger.info(
                f"Fetched batch of {len(results)} DAST results for scan {dast_scan_id}"
            )
            yield [
                self._enrich_scan_result_with_dast_scan_id(
                    result,
                    dast_scan_id,
                )
                for result in results
            ]
