from typing import Any, Dict
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from port_ocean.utils.cache import cache_iterator_result
from checkmarx_one.core.options import ListDastScanOptions


class CheckmarxDastScanExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One DAST scans."""

    def _enrich_dast_scan_with_environment_id(
        self, dast_scan: Dict[str, Any], environment_id: str
    ) -> dict[str, Any]:
        """Enrich DAST scan with environment ID."""
        dast_scan["__environment_id"] = environment_id
        return dast_scan

    async def get_resource(self, options: Any) -> Any:
        raise NotImplementedError("Fetching single DAST scan is not supported")

    @cache_iterator_result()
    async def get_paginated_resources(
        self,
        options: ListDastScanOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        environment_id = options["environment_id"]
        params: dict[str, Any] = {"environmentID": environment_id}
        if groups := options.get("groups"):
            params["groups"] = groups

        async for results in self.client.send_paginated_request(
            "/dast/scans/scans", "scans", params
        ):
            logger.info(f"Fetched batch of {len(results)} DAST scans")
            yield [
                self._enrich_dast_scan_with_environment_id(result, environment_id)
                for result in results
            ]
