from loguru import logger

from github.core.options import ListOrganizationOptions
from github.helpers.exceptions import OrganizationRequiredException
from port_ocean.utils.cache import cache_iterator_result
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class RestOrganizationExporter(AbstractGithubExporter[GithubRestClient]):
    """Exporter for GitHub organizations using REST API."""

    async def is_classic_pat_token(self) -> bool:
        response = await self.client.make_request(f"{self.client.base_url}/user", {})
        return "x-oauth-scopes" in response.headers

    @cache_iterator_result()
    async def get_paginated_resources(
        self, options: ListOrganizationOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info("Fetching organizations")

        organization = options.get("organization")
        multi_organizations = set(options.get("multi_organizations") or [])

        if organization:
            logger.info(f"Fetching single organization {organization}")
            org_data = await self.client.send_api_request(
                f"{self.client.base_url}/orgs/{organization}"
            )
            yield [org_data]
            return

        if not await self.is_classic_pat_token():
            raise OrganizationRequiredException(
                "Organization is required for non-classic PAT tokens"
            )

        list_organizations_url = f"{self.client.base_url}/user/orgs"
        if not multi_organizations:
            logger.info("Fetching all organizations for non-classic PAT tokens")
            async for orgs in self.client.send_paginated_request(
                list_organizations_url
            ):
                yield orgs
            return

        async for orgs in self.client.send_paginated_request(list_organizations_url):
            filtered_orgs = [
                org for org in orgs if org.get("login") in multi_organizations
            ]
            if filtered_orgs:
                logger.info(
                    f"Filtered to {len(filtered_orgs)} organizations from {len(orgs)} total"
                )
                yield filtered_orgs

    async def get_resource[ExporterOptionsT: None](self, options: None) -> RAW_ITEM:
        raise NotImplementedError
