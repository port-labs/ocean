from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger

from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleTeamOptions
from github.helpers.gql_queries import (
    FETCH_TEAM_WITH_MEMBERS_GQL,
    LIST_TEAM_MEMBERS_GQL,
)


class GraphQLTeamWithMembersExporter(AbstractGithubExporter[GithubGraphQLClient]):
    MEMBER_PAGE_SIZE = 30

    async def get_resource[
        ExporterOptionT: SingleTeamOptions
    ](self, options: ExporterOptionT) -> RAW_ITEM:
        variables = {
            "slug": options["slug"],
            "organization": self.client.organization,
            "memberFirst": self.MEMBER_PAGE_SIZE,
        }

        payload = self.client.build_graphql_payload(
            FETCH_TEAM_WITH_MEMBERS_GQL, variables
        )
        response = await self.client.send_api_request(
            self.client.base_url, method="POST", json_data=payload
        )
        if not response:
            return response

        data = response["data"]
        team = data["organization"]["team"]

        members_data = team["members"]
        member_nodes = members_data["nodes"]
        member_page_info = members_data["pageInfo"]

        if member_page_info.get("hasNextPage"):
            all_member_nodes_for_team = await self.get_paginated_members(
                team_slug=team["slug"],
                initial_members_page_info=member_page_info,
                initial_member_nodes=member_nodes,
                member_page_size=self.MEMBER_PAGE_SIZE,
            )
            team["members"]["nodes"] = all_member_nodes_for_team

        del team["members"]["pageInfo"]

        return team

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        variables = {
            "organization": self.client.organization,
            "__path": "organization.teams",
            "memberFirst": self.MEMBER_PAGE_SIZE,
        }

        teams_buffer = []
        async for teams_page_data in self.client.send_paginated_request(
            LIST_TEAM_MEMBERS_GQL, params=variables
        ):
            for team in teams_page_data:
                members_data = team["members"]
                member_nodes = members_data["nodes"]
                member_page_info = members_data["pageInfo"]

                if member_page_info.get("hasNextPage"):
                    all_member_nodes_for_team = await self.get_paginated_members(
                        team_slug=team["slug"],
                        initial_members_page_info=member_page_info,
                        initial_member_nodes=member_nodes,
                        member_page_size=self.MEMBER_PAGE_SIZE,
                    )
                    team["members"]["nodes"] = all_member_nodes_for_team

                del team["members"]["pageInfo"]

                teams_buffer.append(team)

                if len(teams_buffer) >= 10:
                    yield teams_buffer
                    teams_buffer = []

        if teams_buffer:
            yield teams_buffer

    async def get_paginated_members(
        self,
        team_slug: str,
        initial_members_page_info: dict[str, Any],
        initial_member_nodes: list[dict[str, Any]],
        member_page_size: int,
    ) -> list[dict[str, Any]]:
        """
        Fetches all subsequent pages of members for a given team.

        Args:
            team_slug: The slug of the team.
            initial_members_page_info: The pageInfo object from the initial members fetch.
            initial_member_nodes: The list of member nodes from the initial fetch.
            member_page_size: The number of members to fetch per page.

        Returns:
            A complete list of member nodes
        """
        logger.info(f"Fetching additional team members. team_slug='{team_slug}'")

        all_member_nodes = list(initial_member_nodes)
        current_page_info = dict(initial_members_page_info)

        while current_page_info.get("hasNextPage"):
            variables = {
                "organization": self.client.organization,
                "slug": team_slug,
                "memberFirst": member_page_size,
                "memberAfter": current_page_info.get("endCursor"),
            }
            payload = self.client.build_graphql_payload(
                FETCH_TEAM_WITH_MEMBERS_GQL, variables
            )

            response = await self.client.send_api_request(
                self.client.base_url, method="POST", json_data=payload
            )

            team_data = response["data"]["organization"]["team"]

            new_members_data = team_data["members"]
            all_member_nodes.extend(new_members_data["nodes"])
            current_page_info = new_members_data["pageInfo"]

        logger.info(
            f"Successfully fetched {len(all_member_nodes)} members for team '{team_slug}'"
        )
        return all_member_nodes
