from typing import Any, Dict
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import SingleScanResultOptions, ListScanResultOptions


class CheckmarxScanResultExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One scan results.
    Results from this exporter is not meant to be sent in full, only the __scan_id key is meant to be sent.
    This class is not meant to be used directly, it is used as a base class for exporters that have similar functionality.
    """

    def _enrich_scan_result_with_scan_id(
        self, scan_result: Dict[str, Any], scan_id: str
    ) -> dict[str, Any]:
        """Enrich scan result with scan ID."""
        scan_result["__scan_id"] = scan_id
        return scan_result

    async def get_resource(self, options: SingleScanResultOptions) -> RAW_ITEM:

        # No direct events for scan result types, so we rely on scan events and get back scan result types under the scan result with the get_paginated_resources method
        raise NotImplementedError(
            "get_resource method is not implemented for scan result exporter"
        )

    async def _get_paginated_scan_results(
        self,
        params: Dict[str, Any],
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get scan results from Checkmarx One.

        Args:
            options: Options dictionary containing:
                - scan_id: Required scan ID to get results for
                - severity: Filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)
                - state: Filter by state (TO_VERIFY, NOT_EXPLOITABLE, PROPOSED_NOT_EXPLOITABLE, CONFIRMED, URGENT)
                - status: Filter by status (NEW, RECURRENT, FIXED)
                - exclude_result_types: Filter to exclude dev and test dependencies (DEV_AND_TEST, NONE)

        Yields:
            Batches of scan results
        """

        async for results in self.client.send_paginated_request(
            "/results", "results", params
        ):
            logger.info(
                f"Fetched batch of {len(results)} scan results for scan {params['scan-id']}"
            )
            yield results

    async def get_paginated_resources(
        self, options: ListScanResultOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get paginated scan results from Checkmarx One.
        """
        params: dict[str, Any] = self._get_params(options)
        async for results in self._get_paginated_scan_results(params):
            yield [
                self._enrich_scan_result_with_scan_id(
                    result,
                    options["scan_id"],
                )
                for result in results
                if result["type"] == options["type"]
            ]

    def _get_params(self, options: ListScanResultOptions) -> dict[str, Any]:
        params: dict[str, Any] = {
            "scan-id": options["scan_id"],
        }

        if options.get("severity"):
            severity = options.get("severity")
            if isinstance(severity, list) and len(severity) == 1:
                params["severity"] = severity[0]
            else:
                params["severity"] = severity

        if options.get("state"):
            state = options.get("state")
            if isinstance(state, list) and len(state) == 1:
                params["state"] = state[0]
            else:
                params["state"] = state

        if options.get("status"):
            status = options.get("status")
            if isinstance(status, list) and len(status) == 1:
                params["status"] = status[0]
            else:
                params["status"] = status

        if options.get("exclude_result_types"):
            params["exclude-result-types"] = options.get("exclude_result_types")

        return params
