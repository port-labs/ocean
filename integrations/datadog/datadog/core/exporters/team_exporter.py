from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datadog.overrides import TeamResourceConfig

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import (
    GetOptions,
    ListOptions,
    PaginatedExporter,
    SingleResourceExporter,
)
from datadog.incremental import CHANGED_TEAMS_AUDIT_QUERY


class ListTeamOptions(ListOptions["TeamResourceConfig"]):
    include_members: bool = False

    @classmethod
    def from_resource_config(
        cls, resource_config: "TeamResourceConfig"
    ) -> "ListTeamOptions":
        return cls(include_members=resource_config.selector.include_members)


class GetTeamOptions(GetOptions["TeamResourceConfig"]):
    include_members: bool = False

    @classmethod
    def from_resource_config(
        cls, resource_config: "TeamResourceConfig", *, resource_id: str
    ) -> "GetTeamOptions":
        return cls(
            resource_id=resource_id,
            include_members=resource_config.selector.include_members,
        )


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

    async def get_changed_teams(
        self, options: ListTeamOptions, incremental_cursor: datetime
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get teams created or modified, or whose members changed, since
        ``incremental_cursor``, found through audit events. Deleted teams are not
        returned.
        Docs: https://docs.datadoghq.com/api/latest/audit/#search-audit-logs-events
        """
        team_ids = await self._changed_asset_ids(
            CHANGED_TEAMS_AUDIT_QUERY, incremental_cursor
        )
        async for teams in self._get_existing_resources(
            GetTeamOptions(resource_id=team_id, include_members=options.include_members)
            for team_id in team_ids
        ):
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
        url = f"{self.client.api_url}/api/v2/team/{options.resource_id}"
        team_response = await self.client.send_api_request(url)
        team = team_response.get("data")
        if not team:
            return None

        if not options.include_members:
            return team

        members: list[dict[str, Any]] = []
        async for member_batch in self._get_team_members(options.resource_id):
            members.extend(member_batch)
        team["__members"] = members
        return team
