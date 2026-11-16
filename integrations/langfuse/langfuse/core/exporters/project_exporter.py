from typing import Optional

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from langfuse.core.exporters.abstract_exporter import AbstractLangfuseExporter


class ProjectExporter(AbstractLangfuseExporter):
    """Project-scoped API key → single project from GET /projects."""

    async def get_resource(self, options: None = None) -> Optional[RAW_ITEM]:
        response = await self.client.send_api_request("projects")
        projects = response.get("data") or []
        if not projects:
            logger.warning("No Langfuse project returned for configured API key")
            return None
        return projects[0]

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        project = await self.get_resource()
        if project:
            yield [project]
