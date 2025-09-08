from typing import Any
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import ListSastOptions
from checkmarx_one.utils import sast_visible_columns


class CheckmarxSastExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One SAST results."""

    async def get_resource(self, options: Any) -> RAW_ITEM:

        raise NotImplementedError(
            "Single SAST result fetch is not implemented for the SAST exporter."
        )

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
        params = {
            "scan-id": options["scan_id"],
            "visible-columns": sast_visible_columns(),
        }

        # Add optional parameters if provided
        if "compliance" in options and options["compliance"] is not None:
            params["compliance"] = options["compliance"]
        if "group" in options and options["group"] is not None:
            params["group"] = options["group"]
        if "include_nodes" in options:
            params["include-nodes"] = str(options["include_nodes"]).lower()
        if "language" in options and options["language"] is not None:
            params["language"] = options["language"]
        if "result_id" in options and options["result_id"] is not None:
            params["result-id"] = options["result_id"]
        if "severity" in options and options["severity"] is not None:
            params["severity"] = options["severity"]
        if "status" in options and options["status"] is not None:
            params["status"] = options["status"]
        if "category" in options and options["category"] is not None:
            params["category"] = options["category"]
        if "state" in options and options["state"] is not None:
            params["state"] = options["state"]

        return params

