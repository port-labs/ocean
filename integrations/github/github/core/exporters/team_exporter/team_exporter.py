from typing import Any, Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleTeamOptions, ListTeamOptions
from github.helpers.utils import enrich_with_organization, IgnoredError


class RestTeamExporter(AbstractGithubExporter[GithubRestClient]):
    _EXTERNAL_GROUP_IGNORED_ERRORS = [
        IgnoredError(
            status=400,
            message="Organization is not part of an externally managed enterprise",
            type="NOT_EMU_ORG",
        )
    ]

    async def get_resource[ExporterOptionT: SingleTeamOptions](
        self, options: ExporterOptionT
    ) -> Optional[RAW_ITEM]:
        slug = options["slug"]
        organization = options["organization"]

        logger.info(f"Fetching team {slug} from organization {organization}")

        url = f"{self.client.base_url}/orgs/{organization}/teams/{slug}"
        response = await self.client.send_api_request(url)
        if not response:
            logger.warning(
                f"No team found with slug: {slug} in organization {organization}"
            )
            return None

        logger.info(f"Fetched team {slug} from {organization}")
        return enrich_with_organization(response, organization)

    async def get_paginated_resources[ExporterOptionT: ListTeamOptions](
        self, options: ExporterOptionT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        organization = options["organization"]
        url = f"{self.client.base_url}/orgs/{organization}/teams"

        async for teams in self.client.send_paginated_request(url):
            logger.info(f"Fetched {len(teams)} teams from {organization}")

            batch = [enrich_with_organization(team, organization) for team in teams]
            yield batch

    async def get_team_repositories_by_slug[ExporterOptionT: SingleTeamOptions](
        self, options: ExporterOptionT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        organization = options["organization"]
        url = (
            f"{self.client.base_url}/orgs/{organization}/teams/{options['slug']}/repos"
        )
        async for repos in self.client.send_paginated_request(url):
            logger.info(
                f"Fetched {len(repos)} repos for team {options['slug']} from {organization}"
            )
            yield repos

    async def get_team_members_by_slug[ExporterOptionT: SingleTeamOptions](
        self, options: ExporterOptionT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        organization = options["organization"]
        url = f"{self.client.base_url}/orgs/{organization}/teams/{options['slug']}/members"
        async for members in self.client.send_paginated_request(url):
            logger.info(
                f"Fetched {len(members)} members for team {options['slug']} from {organization}"
            )
            yield members

    async def enrich_enterprise_teams_with_members(
        self,
        teams: list[dict[str, Any]],
        organization: str,
    ) -> list[dict[str, Any]]:
        for team in teams:
            if not team["slug"].startswith("ent:"):
                continue
            all_members: list[dict[str, Any]] = []
            async for batch in self.get_team_members_by_slug(
                SingleTeamOptions(organization=organization, slug=team["slug"])
            ):
                all_members.extend(batch)
            team["members"] = {"nodes": all_members}
        return teams

    async def enrich_teams_with_external_group(
        self,
        teams: list[dict[str, Any]],
        organization: str,
    ) -> list[dict[str, Any]]:
        for team in teams:
            slug = team["slug"]
            url = f"{self.client.base_url}/orgs/{organization}/teams/{slug}/external-groups"
            response = await self.client.send_api_request(
                url, ignored_errors=self._EXTERNAL_GROUP_IGNORED_ERRORS
            )
            # Per GitHub docs, only one external group can be linked to a team —
            # no pagination on this endpoint.
            # https://docs.github.com/en/rest/teams/external-groups
            groups = response.get("groups", [])
            if not groups:
                logger.debug(
                    f"No external group linked to team {slug} in {organization}"
                )
                team["__external_group"] = None
                continue
            team["__external_group"] = groups[0]
            logger.info(
                f"Fetched external IdP group {groups[0]['group_name']} for team {slug} in {organization}"
            )
        return teams
