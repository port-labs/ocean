from loguru import logger

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import PaginatedExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class TeamExporter(PaginatedExporter):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info("Getting teams from Linear")
        async for teams in self._paginate_graphql_objects(LinearObject.TEAMS):
            yield teams
