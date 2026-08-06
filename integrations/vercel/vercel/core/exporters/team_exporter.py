"""Team exporter for Vercel integration."""

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from vercel.core.exporters.abstract_exporter import AbstractVercelExporter


class TeamExporter(AbstractVercelExporter):
    """Exporter for Vercel teams."""

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get paginated teams from the API."""
        async for teams_batch in self.client.get_teams():
            logger.info(f"Yielding teams batch of size: {len(teams_batch)}")
            yield teams_batch
