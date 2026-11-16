from typing import Any, Optional

from loguru import logger
from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from langfuse.core.exporters.abstract_exporter import AbstractLangfuseExporter
from langfuse.core.options import ListPromptOptions, SinglePromptOptions

PROMPT_INCREMENTAL = ServerSideTimestampStrategy(param_key="fromUpdatedAt")


class PromptExporter(AbstractLangfuseExporter):
    async def get_resource(self, options: SinglePromptOptions) -> Optional[RAW_ITEM]:
        name = options["name"]
        # Catalog entity is PromptMeta (list), not a single version body.
        async for batch in self.client.send_paginated_request(
            "v2/prompts", params={"name": name, "limit": 1}
        ):
            if batch:
                return batch[0]
            break
        logger.warning(f"Langfuse prompt not found: {name}")
        return None

    async def get_paginated_resources(
        self, options: ListPromptOptions | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params: dict[str, Any] = {}
        if options:
            if options.get("from_updated_at"):
                params["fromUpdatedAt"] = options["from_updated_at"]
            if options.get("label"):
                params["label"] = options["label"]
            if options.get("tag"):
                params["tag"] = options["tag"]

        async for batch in self.client.send_paginated_request(
            "v2/prompts", params=params
        ):
            yield batch
