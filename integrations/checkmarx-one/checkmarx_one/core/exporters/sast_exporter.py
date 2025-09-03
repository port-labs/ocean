from typing import Any, List
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import SingleSastOptions, ListSastOptions
from checkmarx_one.utils import sast_visible_columns


class CheckmarxSastExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One SAST results."""

    async def get_resource(self, options: SingleSastOptions) -> RAW_ITEM:
        """Get a specific SAST result by result hash within a scan."""
        params = {
            "scan-id": options["scan_id"],
            "result-id": options["result_id"],
            "limit": 1,
        }
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

        params: dict[str, Any] = self._build_params(options)
        logger.warning(f"SAST params: {params}")
        async for results in self.client.send_paginated_request(
            "/sast-results/",
            "results",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(results)} SAST results for scan {options['scan_id']}"
            )
            # logger.warning(f"SAST results: {results}")
            yield results

    def _build_params(self, options: ListSastOptions) -> dict[str, Any]:
        """Build query params for SAST listing, including desired visible columns."""
        return {
            "scan-id": options["scan_id"],
            "visible-columns": sast_visible_columns(),
        }
