from typing import Any, Dict
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import ListKicsOptions
from checkmarx_one.core.exporters.utils import enrich_result_with_metadata


class CheckmarxKicsExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One KICS (IaC Security) scan results."""

    def _build_params(self, options: ListKicsOptions) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "scan-id": options["scan_id"],
        }

        # Apply optional filters if provided
        if severity := options.get("severity"):
            params["severity"] = severity
        if status := options.get("status"):
            params["status"] = status

        return params

    def get_resource(self, options: Any) -> Any:
        raise NotImplementedError(
            "Single KICS result fetch is not implemented for the KICS exporter."
        )

    async def get_paginated_resources(
        self,
        options: ListKicsOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get KICS results for a scan from Checkmarx One.

        Args:
            options: Options including required scan_id and optional filters.

        Yields:
            Batches of KICS results (list of dicts).
        """

        params = self._build_params(options)
        async for results in self.client.send_paginated_request(
            "/kics-results", "results", params
        ):
            logger.info(
                f"Fetched batch of {len(results)} KICS results for scan {options['scan_id']}"
            )
            yield [
                enrich_result_with_metadata(
                    result, self.client.ui_base_url, options["scan_id"]
                )
                for result in results
            ]
