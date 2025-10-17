from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleTeamOptions, ListTeamOptions


class RestTeamExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[
        ExporterOptionT: SingleTeamOptions
    ](self, options: ExporterOptionT) -> RAW_ITEM:
        slug = options["slug"]
        organization = options["organization"]

        logger.info(f"Fetching team {slug} from organization {organization}")

        url = f"{self.client.base_url}/orgs/{organization}/teams/{slug}"
        response = await self.client.send_api_request(url)

        logger.info(f"Fetched team {slug} from {organization}")
        return response

    async def get_paginated_resources[
        ExporterOptionT: ListTeamOptions
    ](self, options: ExporterOptionT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        organization = options["organization"]
        url = f"{self.client.base_url}/orgs/{organization}/teams"

        async for teams in self.client.send_paginated_request(url):
            logger.info(f"Fetched {len(teams)} teams from {organization}")
            yield teams

    async def get_team_repositories_by_slug[
        ExporterOptionT: SingleTeamOptions
    ](self, options: ExporterOptionT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        organization = options["organization"]
        url = (
            f"{self.client.base_url}/orgs/{organization}/teams/{options['slug']}/repos"
        )
        async for repos in self.client.send_paginated_request(url):
            logger.info(
                f"Fetched {len(repos)} repos for team {options['slug']} from {organization}"
            )
            yield repos
