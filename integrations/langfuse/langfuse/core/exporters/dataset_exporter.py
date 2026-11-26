from typing import Optional
from urllib.parse import quote

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from langfuse.core.exporters.abstract_exporter import AbstractLangfuseExporter
from langfuse.core.options import SingleDatasetOptions


class DatasetExporter(AbstractLangfuseExporter):
    async def get_resource(self, options: SingleDatasetOptions) -> Optional[RAW_ITEM]:
        encoded = quote(options["name"], safe="")
        result = await self.client.send_api_request(f"v2/datasets/{encoded}")
        if not result:
            logger.warning(f"Langfuse dataset not found: {options['name']}")
            return None
        return result

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch in self.client.send_paginated_request("v2/datasets"):
            yield batch
