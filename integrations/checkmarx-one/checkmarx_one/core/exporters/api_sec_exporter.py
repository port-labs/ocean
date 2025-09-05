from typing import Any, Dict
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import SingleApiSecOptions, ListApiSecOptions


class CheckmarxApiSecExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One API Security risks."""

    def _enrich_scan_result_with_scan_id(
        self, scan_result: Dict[str, Any], scan_id: str
    ) -> dict[str, Any]:
        """Enrich scan result with scan ID."""
        scan_result["__scan_id"] = scan_id
        return scan_result

    async def get_resource(self, options: SingleApiSecOptions) -> RAW_ITEM:
        """
        Get a specific API sec risk by ID.

        Args:
            options: Options containing risk_id

        Returns:
            The API sec risk details
        """

        response = await self.client.send_api_request(
            f"/apisec/static/api/risks/risk/{options['risk_id']}",
        )
        logger.info(f"Fetched API sec risk {options['risk_id']}")
        return response

    async def get_paginated_resources(
        self,
        options: ListApiSecOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get API Security risks from Checkmarx One.

        Args:
            options: Options dictionary containing:
                - scan_id: Required scan ID to get results for
                - filtering: Optional filter by fields
                - searching: Optional full text search
                - sorting: Optional sorting direction
        Yields:
            Batches of API sec risks
        """

        scan_id = options["scan_id"]
        async for results in self.client.send_paginated_request_api_sec(
            f"/apisec/static/api/risks/{scan_id}", "entries"
        ):
            logger.info(
                f"Fetched batch of {len(results)} API sec risks for scan {options['scan_id']}"
            )
            yield [
                self._enrich_scan_result_with_scan_id(
                    result,
                    options["scan_id"],
                )
                for result in results
            ]
