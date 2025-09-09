from typing import Any, Dict
import json
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import SingleDastOptions, ListDastOptions


class CheckmarxDastExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One DAST results."""

    def _enrich_dast_result_with_scan_id(
        self, result: Dict[str, Any], scan_id: str
    ) -> dict[str, Any]:
        """Enrich DAST result with scan ID."""
        result["__scan_id"] = scan_id
        return result

    async def get_resource(self, options: SingleDastOptions) -> RAW_ITEM:
        scan_id = options["scan_id"]
        result_id = options["result_id"]
        endpoint = f"/dast/mfe-results/results/info/{result_id}/{scan_id}"
        response = await self.client.send_api_request(endpoint)
        logger.info(f"Fetched DAST result {result_id} for scan {scan_id}")
        return self._enrich_dast_result_with_scan_id(response, scan_id)

    async def get_paginated_resources(
        self,
        options: ListDastOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get DAST results from Checkmarx One, handling pagination internally."""

        scan_id = options["scan_id"]
        params: dict[str, Any] = {}
        if filters := options.get("filter"):
            params["filter"] = json.dumps(filters)

        try:
            async for results in self.client.send_paginated_request_dast(
                f"/dast/mfe-results/results/{scan_id}",
                "results",
                params,
            ):
                logger.info(
                    f"Fetched batch of {len(results)} DAST results for scan {scan_id}"
                )
                yield [
                    self._enrich_dast_result_with_scan_id(result, scan_id)
                    for result in results
                ]
        except Exception as e:
            # Handle cases where scan doesn't have DAST results (404 errors)
            if "404" in str(e) or "failed to find scanID" in str(e):
                logger.debug(f"No DAST results found for scan {scan_id}: {str(e)}")
                return
            else:
                # Re-raise other errors
                logger.error(
                    f"Error fetching DAST results for scan {scan_id}: {str(e)}"
                )
                raise
