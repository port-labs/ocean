from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleTeamOptions
from github.helpers.gql_queries import (
    FETCH_TEAM_WITH_MEMBERS_GQL,
    LIST_TEAM_MEMBERS_GQL,
)


class GraphQLTeamExporter(AbstractGithubExporter[GithubGraphQLClient]):
    async def get_resource[ExporterOptionT: SingleTeamOptions](
        self, options: ExporterOptionT
    ) -> RAW_ITEM:
        variables = {"slug": options["slug"], "organization": self.client.organization}
        payload = self.client.build_graphql_payload(
            FETCH_TEAM_WITH_MEMBERS_GQL, variables
        )
        res = await self.client.send_api_request(
            self.client.base_url, method="POST", json_data=payload
        )
        data = res.json()
        return data["data"]["organization"]["team"]

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        # Define desired page sizes.
        team_page_size = 25  # Example page size for teams list
        member_page_size = 25 # Example page size for members within each team

        variables = {
            "organization": self.client.organization,
            "__path": "organization.teams",  # Used by send_paginated_request for team pageInfo
            "teamFirst": team_page_size,     # Corresponds to $teamFirst in LIST_TEAM_MEMBERS_GQL
            "memberFirst": member_page_size  # Corresponds to $memberFirst in LIST_TEAM_MEMBERS_GQL
        }
        async for teams_page_data in self.client.send_paginated_request(
            LIST_TEAM_MEMBERS_GQL, params=variables  # This yields a list of teams
        ):
            processed_teams_page = []
            for team in teams_page_data:  # Iterate through teams in the current page of teams
                members_data = team.get("members", {})
                member_nodes = members_data.get("nodes", [])
                member_page_info = members_data.get("pageInfo", {})

                if member_page_info.get("hasNextPage"):
                    # Fetch all remaining members for this specific team
                    all_member_nodes_for_team, final_member_page_info = await self.fetch_other_members(
                        team_slug=team["slug"],
                        initial_members_page_info=member_page_info,
                        initial_member_nodes=member_nodes,
                        member_page_size=member_page_size
                    )
                    team["members"]["nodes"] = all_member_nodes_for_team
                    team["members"]["pageInfo"] = final_member_page_info

                processed_teams_page.append(team)
            yield processed_teams_page

    async def fetch_other_members(
        self, team_slug: str, initial_members_page_info: dict, initial_member_nodes: list, member_page_size: int = 25
    ) -> tuple[list, dict]:
        """
        Fetches all subsequent pages of members for a given team.

        Args:
            team_slug: The slug of the team.
            initial_members_page_info: The pageInfo object from the initial members fetch.
            initial_member_nodes: The list of member nodes from the initial fetch.
            member_page_size: The number of members to fetch per page.

        Returns:
            A tuple containing the complete list of member nodes and the final pageInfo object.
        """
        all_member_nodes = list(initial_member_nodes)
        current_page_info = dict(initial_members_page_info)
        # final_page_info will be updated with the pageInfo from the last successful fetch
        final_page_info = current_page_info

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
            
            # This query fetches the team object again, including the next page of its members.
            response = await self.client.send_api_request(
                self.client.base_url, method="POST", json_data=payload
            )
            response_data = response.json()

            if "errors" in response_data:
                # Handle or log GraphQL errors. For now, stop fetching for this team.
                # Consider logging: self.logger.error(f"GraphQL error fetching members for team {team_slug}: {response_data['errors']}")
                break
            
            team_data = response_data.get("data", {}).get("organization", {}).get("team")
            if not team_data or "members" not in team_data:
                # Handle unexpected response structure.
                # Consider logging: self.logger.warning(f"Unexpected response structure for team {team_slug} members pagination.")
                break

            new_members_data = team_data["members"]
            all_member_nodes.extend(new_members_data.get("nodes", []))
            current_page_info = new_members_data.get("pageInfo", {})
            final_page_info = current_page_info # Update with the latest pageInfo

        return all_member_nodes, final_page_info
