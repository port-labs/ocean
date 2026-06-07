from loguru import logger
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from datadog.overrides import TeamResourceConfig

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import (
    GetOptions,
    ListOptions,
    PaginatedExporter,
    SingleResourceExporter,
)


class ListTeamOptions(ListOptions["TeamResourceConfig"]):
    include_members: bool = False

    @classmethod
    def from_resource_config(
        cls, resource_config: "TeamResourceConfig"
    ) -> "ListTeamOptions":
        return cls(include_members=resource_config.selector.include_members)


class GetTeamOptions(GetOptions["TeamResourceConfig"]):
    id: str
    include_members: bool = False

    @classmethod
    def from_resource_config(
        cls, resource_config: "TeamResourceConfig", *, id: str
    ) -> "GetTeamOptions":
        return cls(id=id, include_members=resource_config.selector.include_members)


class TeamExporter(
    PaginatedExporter[ListTeamOptions], SingleResourceExporter[GetTeamOptions]
):
    async def get_paginated_resources(
        self, options: ListTeamOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get teams from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/teams/#get-all-teams
        """
        include_members = options.include_members
        url = f"{self.client.api_url}/api/v2/team"

        async for teams in self._paginate_by_page_param(url):
            if include_members:
                for team in teams:
                    members = []
                    async for member_batch in self._get_team_members(team["id"]):
                        members.extend(member_batch)
                    team["__members"] = members

            yield teams

    async def _get_team_members(self, team_id: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get team memberships from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/teams/#get-team-memberships
        """
        logger.info(f"Enriching team {team_id} with members information")
        url = f"{self.client.api_url}/api/v2/team/{team_id}/memberships"
        async for batch in self._paginate_by_page_param(url, data_key="included"):
            yield batch

    async def get_resource(self, options: GetTeamOptions) -> dict[str, Any] | None:
        """Get a single team by ID.
        Docs: https://docs.datadoghq.com/api/latest/teams/#get-a-team-link
        """
        url = f"{self.client.api_url}/api/v2/team/{options.id}"
        team_response = await self.client.send_api_request(url)
        team = team_response.get("data")
        if not team:
            return None

        if not options.include_members:
            return team

        members: list[dict[str, Any]] = []
        async for member_batch in self._get_team_members(options.id):
            members.extend(member_batch)
        team["__members"] = members
        return team
