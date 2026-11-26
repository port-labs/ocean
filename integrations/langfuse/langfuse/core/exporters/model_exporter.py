from typing import Optional

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from langfuse.core.exporters.abstract_exporter import AbstractLangfuseExporter
from langfuse.core.options import SingleModelOptions


class ModelExporter(AbstractLangfuseExporter):
    async def get_resource(self, options: SingleModelOptions) -> Optional[RAW_ITEM]:
        result = await self.client.send_api_request(f"models/{options['model_id']}")
        if not result:
            logger.warning(f"Langfuse model not found: {options['model_id']}")
            return None
        return result

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch in self.client.send_paginated_request("models"):
            yield batch
