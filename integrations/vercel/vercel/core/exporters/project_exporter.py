"""Project exporter for Vercel integration."""

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from vercel.core.exporters.abstract_exporter import AbstractVercelExporter


class ProjectExporter(AbstractVercelExporter):
    """Exporter for Vercel projects."""

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get paginated projects from the API."""
        async for projects_batch in self.client.get_projects():
            logger.info(f"Yielding projects batch of size: {len(projects_batch)}")
            yield projects_batch
