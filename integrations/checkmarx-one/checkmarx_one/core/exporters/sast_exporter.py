from typing import Any, List
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import SingleSastOptions, ListSastOptions


class CheckmarxSastExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One SAST results."""

    async def get_resource(self, options: SingleSastOptions) -> RAW_ITEM:
        """Get a specific SAST result by result hash within a scan."""
        params = self._build_single_resource_params(options)
        response = await self.client.send_api_request(
            "/sast-results/",
            params=params,
        )
        if isinstance(response, dict) and "results" in response:
            results: List[dict[str, Any]] = response.get("results", [])
            item = results[0] if results else {}
        else:
            item = response
        logger.info(f"Fetched SAST result by result-id for scan {options['scan_id']}")
        return item

    async def get_paginated_resources(
        self,
        options: ListSastOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get SAST results from Checkmarx One.

        Args:
            options: Includes required scan_id and optional filters per API spec.
        Yields:
            Batches of SAST results
        """

        params: dict[str, Any] = self._build_paginated_resource_params(options)
        async for results in self.client.send_paginated_request(
            "/sast-results/",
            "results",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(results)} SAST results for scan {options['scan_id']}"
            )
            yield results

    def _build_paginated_resource_params(
        self, options: ListSastOptions
    ) -> dict[str, Any]:
        """Build query params for SAST listing, including desired visible columns."""
        return {
            "scan-id": options["scan_id"],
            **options,
        }

    def _build_single_resource_params(
        self, options: SingleSastOptions
    ) -> dict[str, Any]:
        """Build query params for SAST single resource."""
        params: dict[str, Any] = {
            "scan-id": options["scan_id"],
            **options,
        }
        return params
