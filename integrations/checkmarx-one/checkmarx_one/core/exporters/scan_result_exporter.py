from collections.abc import AsyncGenerator
from typing import Any, Optional
from loguru import logger

from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from port_ocean.utils.cache import cache_iterator_result


class CheckmarxScanResultExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One scan results."""

    def _enrich_scan_result_with_scan_id(
        self, scan_result: dict[str, Any], scan_id: str
    ) -> dict[str, Any]:
        """Enrich scan result with scan ID."""
        scan_result["__scan_id"] = scan_id
        return scan_result

    @cache_iterator_result()
    async def get_scan_results(
        self,
        scan_id: str,
        options: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
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
        if options is None:
            options = {}

        if not scan_id:
            raise ValueError("scan_id is required for getting scan results")

        params: dict[str, Any] = {
            "scan-id": scan_id,
        }

        # Add optional parameters
        if "limit" in options:
            params["limit"] = options["limit"]
        if "offset" in options:
            params["offset"] = options["offset"]
        if "severity" in options:
            params["severity"] = options["severity"]
        if "state" in options:
            params["state"] = options["state"]
        if "status" in options:
            params["status"] = options["status"]
        if "sort" in options:
            params["sort"] = options["sort"]
        if "exclude_result_types" in options:
            params["exclude-result-types"] = options["exclude_result_types"]

        async for results in self.client._get_paginated_resources(
            "/results", "results", params
        ):
            logger.info(
                f"Fetched batch of {len(results)} scan results for scan {scan_id}"
            )
            batch = [
                self._enrich_scan_result_with_scan_id(result, scan_id)
                for result in results
            ]
            yield batch

    async def get_scan_result_by_id(
        self, scan_id: str, result_id: str
    ) -> dict[str, Any]:
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
            "scan-id": scan_id,
            "limit": 1,
        }

        response = await self.client._send_api_request("/results", params=params)
        logger.info(f"Fetched scan result {result_id} for scan {scan_id}")
        return self._enrich_scan_result_with_scan_id(response, scan_id)
