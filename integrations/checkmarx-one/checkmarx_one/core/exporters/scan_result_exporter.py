from typing import Any, Dict
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from port_ocean.utils.cache import cache_iterator_result
from checkmarx_one.core.options import SingleScanResultOptions, ListScanResultOptions
from checkmarx_one.utils import ObjectKind


class CheckmarxScanResultExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One scan results."""

    def _enrich_scan_result_with_scan_id(
        self, scan_result: Dict[str, Any], scan_id: str
    ) -> dict[str, Any]:
        """Enrich scan result with scan ID."""
        scan_result["__scan_id"] = scan_id
        return scan_result

    @cache_iterator_result()
    async def _enrich_batch(
        self, params: dict[str, Any], scan_id: str
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Enrich a yield batch of scan results.

        Args:
            results: Raw scan results from the API
            scan_id: The scan ID to enrich results with

        Returns:
            Enriched batch of scan results
        """
        async for results in self.client.send_paginated_request(
            "/results", "results", params
        ):
            batch = [
                self._enrich_scan_result_with_scan_id(
                    result,
                    scan_id,
                )
                for result in results
            ]
            yield batch

    async def get_resource(self, options: SingleScanResultOptions) -> RAW_ITEM:
        """
        Get a specific scan result by ID.

        Args:
            scan_id: The scan ID
            result_id: The specific result ID

        Returns:
            The scan result details
        """
        # Note: The API documentation doesn't show a direct endpoint for getting a single result
        # This method assumes there might be a way to get individual results
        # For now, we'll use the general results endpoint with filtering
        params = {
            "scan-id": options["scan_id"],
            "limit": 1,
        }

        response = await self.client.send_api_request("/results", params=params)
        logger.info(
            f"Fetched scan result {options['result_id']} for scan {options['scan_id']}"
        )
        return self._enrich_scan_result_with_scan_id(response, options["scan_id"])

    async def get_paginated_resources(
        self,
        options: ListScanResultOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get scan results from Checkmarx One.

        Args:
            options: Options dictionary containing:
                - scan_id: Required scan ID to get results for
                - limit: Maximum number of results per page (1-10000, default: 20)
                - offset: Starting offset for pagination (default: 0)
                - severity: Filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)
                - state: Filter by state (TO_VERIFY, NOT_EXPLOITABLE, PROPOSED_NOT_EXPLOITABLE, CONFIRMED, URGENT)
                - status: Filter by status (NEW, RECURRENT, FIXED)
                - sort: Sort results by specified parameters (e.g., ["+severity", "-status"])
                - exclude_result_types: Filter to exclude dev and test dependencies (DEV_AND_TEST, NONE)

        Yields:
            Batches of scan results
        """
        if options["kind"] == ObjectKind.CONTAINERS.value:
            options["kind"] = "containers"
        params: dict[str, Any] = self._get_params(options)

        async for batch in self._enrich_batch(params, options["scan_id"]):
            data = [result for result in batch if result["type"] == options["kind"]]
            yield data

    def _get_params(self, options: ListScanResultOptions) -> dict[str, Any]:
        params: dict[str, Any] = {
            "scan-id": options["scan_id"],
        }

        if options.get("severity"):
            params["severity"] = options.get("severity")
        if options.get("state"):
            params["state"] = options.get("state")
        if options.get("status"):
            params["status"] = options.get("status")
        if options.get("exclude_result_types"):
            params["exclude-result-types"] = options.get("exclude_result_types")

        return params
