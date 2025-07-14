from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleTeamOptions
from github.helpers.gql_queries import (
    FETCH_TEAM_WITH_MEMBERS_GQL,
    LIST_TEAM_MEMBERS_GQL,
    SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL,
)


class RestTeamExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[
        ExporterOptionT: SingleTeamOptions
    ](self, options: ExporterOptionT) -> RAW_ITEM:
        slug = options["slug"]
        organization = self.client.organization

        url = f"{self.client.base_url}/orgs/{organization}/teams/{slug}"
        response = await self.client.send_api_request(url)

        logger.info(f"Fetched team {slug} from {organization}")
        return response

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        url = f"{self.client.base_url}/orgs/{self.client.organization}/teams"
        async for teams in self.client.send_paginated_request(url):
            yield teams

    async def get_team_repositories_by_slug[
        ExporterOptionT: SingleTeamOptions
    ](self, options: ExporterOptionT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        url = f"{self.client.base_url}/orgs/{self.client.organization}/teams/{options['slug']}/repos"
        async for repos in self.client.send_paginated_request(url):
            logger.info(f"Fetched {len(repos)} repos for team {options['slug']}")
            yield repos


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

    async def get_team_member_repositories(self, team_slug: str) -> RAW_ITEM:
        team_data = None
        all_members = {}
        all_repos = {}
        member_after = None
        repo_after = None
        members_complete = False
        initial_repo_after = None

        while True:
            # If we're still paginating members, ensure repoAfter is None
            if not members_complete:
                repo_after = None

            variables = {
                "slug": team_slug,
                "organization": self.client.organization,
                "memberFirst": self.MEMBER_PAGE_SIZE,
                "memberAfter": member_after,
                "repoFirst": self.MEMBER_PAGE_SIZE,
                "repoAfter": repo_after,
            }

            payload = self.client.build_graphql_payload(
                SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL, variables
            )

            response = await self.client.send_api_request(
                self.client.base_url, method="POST", json_data=payload
            )
            if not response:
                return {}

            team = response.get("data", {}).get("organization", {}).get("team")
            if team is None:
                return {}

            if team_data is None:
                team_data = dict(team)

            # Handle member pagination
            members_data = team.get("members", {})
            members_page_info = members_data.get("pageInfo", {})
            for member in members_data.get("nodes", []):
                all_members[member["id"]] = member

            member_after = (
                members_page_info.get("endCursor")
                if members_page_info.get("hasNextPage")
                else None
            )

            # Handle repository pagination
            repos_data = team.get("repositories", {})
            repos_page_info = repos_data.get("pageInfo", {})
            for repo in repos_data.get("nodes", []):
                all_repos[repo["id"]] = repo

            # Store the initial repo_after value from the first page
            if initial_repo_after is None:
                initial_repo_after = (
                    repos_page_info.get("endCursor")
                    if repos_page_info.get("hasNextPage")
                    else None
                )

            repo_after = (
                repos_page_info.get("endCursor")
                if repos_page_info.get("hasNextPage")
                else None
            )

            # If member pagination is complete and we haven't started repo pagination yet
            if not member_after and not members_complete:
                members_complete = True
                member_after = None
                # Only start repo pagination if there is a next page for repos
                if initial_repo_after is not None:
                    repo_after = initial_repo_after
                    continue
                else:
                    break

            # Break if all pages fetched
            if not member_after and not repo_after:
                break

        team_data["members"] = {"nodes": list(all_members.values())}
        team_data["repositories"] = {"nodes": list(all_repos.values())}

        return team_data
