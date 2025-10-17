from loguru import logger

from github.core.options import ListOrganizationOptions
from github.helpers.exceptions import OrganizationRequiredException
from port_ocean.utils.cache import cache_iterator_result
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from typing import List


class RestOrganizationExporter(AbstractGithubExporter[GithubRestClient]):
    """Exporter for GitHub organizations using REST API."""

    async def is_classic_pat_token(self) -> bool:
        response = await self.client.make_request(f"{self.client.base_url}/user", {})
        return "x-oauth-scopes" in response.headers

    @cache_iterator_result()
    async def get_paginated_resources(
        self, options: ListOrganizationOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        If the organization is provided, fetch a single organization.
        If the organization is not provided, fetch all organizations.
        If the organization is not provided and the token is not a classic PAT token, raise an error.
        If the organization is provided and the token is not a classic PAT token, raise an error.
        If the organization is not provided and the token is a classic PAT token, fetch all organizations.
        If the organization is provided and the token is a classic PAT token, fetch a single organization.
        """
        logger.info("Fetching organizations")

        list_organizations_url = f"{self.client.base_url}/user/orgs"
        allowed_multi_organizations: List[str] = options.get(
            "allowed_multi_organizations", []
        )

        if organization := options.get("organization"):
            logger.info(f"Fetching single organization {organization}")
            yield [
                await self.client.send_api_request(
                    f"{self.client.base_url}/orgs/{organization}"
                )
            ]
            return

        if not await self.is_classic_pat_token():
            raise OrganizationRequiredException(
                "Organization is required for non-classic PAT tokens"
            )

        async for orgs in self.client.send_paginated_request(list_organizations_url):
            # if allowed_multi_organizations is provided, filter the organizations, else yield all organizations
            if allowed_multi_organizations:
                orgs = [
                    org
                    for org in orgs
                    if org.get("login") in allowed_multi_organizations
                ]
            yield orgs

    async def get_resource[ExporterOptionsT: None](self, options: None) -> RAW_ITEM:
        raise NotImplementedError
