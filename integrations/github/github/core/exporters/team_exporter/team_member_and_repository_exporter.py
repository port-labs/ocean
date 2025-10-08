from dataclasses import dataclass, field
from typing import Any, Optional, Dict

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger

from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleTeamOptions
from github.helpers.gql_queries import SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL


@dataclass
class TeamFetchState:
    team_slug: str
    team_data: Optional[dict[str, Any]] = None
    all_members: Dict[str, dict[str, Any]] = field(default_factory=dict)
    all_repos: Dict[str, dict[str, Any]] = field(default_factory=dict)
    member_after: Optional[str] = None
    repo_after: Optional[str] = None
    members_complete: bool = False
    initial_repo_after: Optional[str] = None


class GraphQLTeamMembersAndReposExporter(AbstractGithubExporter[GithubGraphQLClient]):
    """
    This exporter fetches a team with its members and repositories.
    Its an enrichment exporter and should be used in that context only.
    """

    PAGE_SIZE = 30

    async def get_resource[
        ExporterOptionT: SingleTeamOptions
    ](self, options: ExporterOptionT) -> RAW_ITEM:
        return await self._fetch_team_with_members_and_repositories(options["slug"])

    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise NotImplementedError("This exporter does not support pagination")

    async def _fetch_team_with_members_and_repositories(
        self, team_slug: str
    ) -> dict[str, Any]:
        logger.info(f"Fetching team '{team_slug}' with members and repositories")

        state = TeamFetchState(team_slug=team_slug)

        while True:
            logger.debug(
                f"Fetching next page for team '{team_slug}' - members_complete: {state.members_complete}, member_after: {state.member_after}, repo_after: {state.repo_after}"
            )

            response = await self._fetch_next_team_page(state)

            if not response:
                logger.warning(f"No response received for team '{team_slug}'")
                return {}

            team = response.get("data", {}).get("organization", {}).get("team")
            if not team:
                logger.warning(f"No team data found in response for team '{team_slug}'")
                return {}

            if state.team_data is None:
                state.team_data = dict(team)
                logger.debug(f"Initialized team data for '{team_slug}'")

            self._merge_members(state, team.get("members", {}))
            self._merge_repositories(state, team.get("repositories", {}))

            logger.debug(
                f"Current progress for team '{team_slug}': {len(state.all_members)} members, {len(state.all_repos)} repositories"
            )

            if not state.member_after and not state.members_complete:
                state.members_complete = True
                logger.info(
                    f"Completed fetching all members for team '{team_slug}', switching to repositories"
                )
                if state.initial_repo_after:
                    state.repo_after = state.initial_repo_after
                    continue
                else:
                    break

            if not self._has_more_pages(state):
                logger.info(f"No more pages to fetch for team '{team_slug}'")
                break

        state.team_data["members"] = {"nodes": list(state.all_members.values())}
        state.team_data["repositories"] = {"nodes": list(state.all_repos.values())}

        logger.info(
            f"Fetched {len(state.all_members)} members and {len(state.all_repos)} repositories for team '{team_slug}'"
        )
        return state.team_data

    async def _fetch_next_team_page(self, state: TeamFetchState) -> dict[str, Any]:
        if not state.members_complete:
            state.repo_after = None

        variables = {
            "organization": options["organization"],
            "slug": state.team_slug,
            "memberFirst": self.PAGE_SIZE,
            "memberAfter": state.member_after,
            "repoFirst": self.PAGE_SIZE,
            "repoAfter": state.repo_after,
        }

        payload = self.client.build_graphql_payload(
            SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL, variables
        )
        return await self.client.send_api_request(
            self.client.base_url, method="POST", json_data=payload
        )

    def _merge_members(
        self, state: TeamFetchState, members_data: dict[str, Any]
    ) -> None:
        for member in members_data.get("nodes", []):
            state.all_members[member["id"]] = member

        page_info = members_data.get("pageInfo", {})
        state.member_after = (
            page_info.get("endCursor") if page_info.get("hasNextPage") else None
        )

    def _merge_repositories(
        self, state: TeamFetchState, repos_data: dict[str, Any]
    ) -> None:
        for repo in repos_data.get("nodes", []):
            state.all_repos[repo["id"]] = repo

        page_info = repos_data.get("pageInfo", {})

        if state.initial_repo_after is None:
            state.initial_repo_after = (
                page_info.get("endCursor") if page_info.get("hasNextPage") else None
            )

        state.repo_after = (
            page_info.get("endCursor") if page_info.get("hasNextPage") else None
        )

    def _has_more_pages(self, state: TeamFetchState) -> bool:
        return bool(state.member_after or state.repo_after)
