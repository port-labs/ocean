from typing import TYPE_CHECKING

from loguru import logger

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import ListOptions, PaginatedExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

if TYPE_CHECKING:
    from integration import TeamResourceConfig


class ListTeamOptions(ListOptions["TeamResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "TeamResourceConfig"
    ) -> "ListTeamOptions":
        return cls()


class TeamExporter(PaginatedExporter[ListTeamOptions]):
    async def get_paginated_resources(
        self, options: ListTeamOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info("Getting teams from Linear")
        async for teams in self._paginate_graphql_objects(
            LinearObject.TEAMS, page_size=options.page_size
        ):
            yield teams
