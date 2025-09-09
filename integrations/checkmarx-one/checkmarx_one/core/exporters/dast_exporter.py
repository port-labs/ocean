from typing import Any
import json
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import SingleDastOptions, ListDastOptions


class CheckmarxDastExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One DAST results."""

    async def get_resource(self, options: SingleDastOptions) -> RAW_ITEM:
        scan_id = options["scan_id"]
        result_id = options["result_id"]
        endpoint = f"/dast/mfe-results/results/info/{result_id}/{scan_id}"
        response = await self.client.send_api_request(endpoint)
        logger.info(f"Fetched DAST result {result_id} for scan {scan_id}")
        return response

    async def get_paginated_resources(
        self,
        options: ListDastOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get DAST results from Checkmarx One, handling pagination internally."""

        scan_id = options["scan_id"]
        params: dict[str, Any] = {}
        if (filters := options.get("filter")):
            params["filter"] = json.dumps(filters)

        async for results in self.client.send_paginated_request_dast(
            f"/dast/mfe-results/results/{scan_id}",
            "results",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(results)} DAST results for scan {scan_id}"
            )
            yield results

from typing import Any
import json
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import SingleDastOptions, ListDastOptions


class CheckmarxDastExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One DAST results."""

    async def get_resource(self, options: SingleDastOptions) -> RAW_ITEM:
        scan_id = options["scan_id"]
        result_id = options["result_id"]
        endpoint = f"/dast/mfe-results/results/info/{result_id}/{scan_id}"
        response = await self.client.send_api_request(endpoint)
        logger.info(f"Fetched DAST result {result_id} for scan {scan_id}")
        return response

    async def get_paginated_resources(
        self,
        options: ListDastOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get DAST results from Checkmarx One, handling pagination internally."""

        scan_id = options["scan_id"]

        params: dict[str, Any] = {}
        if (search := options.get("search")) is not None:
            params["search"] = search
        if filters := options.get("filter"):
            # API expects a single "filter" object; pass as JSON string
            params["filter"] = json.dumps(filters)

        async for results in self.client.send_paginated_request_dast(
            f"/dast/mfe-results/results/{scan_id}",
            "results",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(results)} DAST results for scan {scan_id}"
            )
            yield results
