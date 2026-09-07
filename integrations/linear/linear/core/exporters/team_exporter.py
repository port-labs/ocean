from loguru import logger

from linear.client.constants import LinearObject
from linear.client.pagination import paginate_graphql_objects
from linear.core.exporters.base_exporter import LinearExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class TeamExporter(LinearExporter):
    async def get_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info("Getting teams from Linear")
        async for teams in paginate_graphql_objects(self.graphql, LinearObject.TEAMS):
            yield teams
