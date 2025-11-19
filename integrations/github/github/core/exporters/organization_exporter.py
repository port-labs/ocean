from loguru import logger

from github.core.options import ListOrganizationOptions
from github.helpers.exceptions import OrganizationRequiredException
from port_ocean.utils.cache import cache_iterator_result, cache_coroutine_result
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from typing import List


class RestOrganizationExporter(AbstractGithubExporter[GithubRestClient]):
    """Exporter for GitHub organizations using REST API."""

    async def is_classic_pat_token(self) -> bool:
        response = await self.client.make_request(f"{self.client.base_url}/user", {})
        return "x-oauth-scopes" in response.headers

    @cache_coroutine_result()
    async def get_personal_org(self) -> RAW_ITEM:
        """
        Fetch the personal account of the authenticated user.
        This method is cached to avoid repeated API calls.
        """
        logger.info("Fetching personal account")
        response = await self.client.send_api_request(f"{self.client.base_url}/user")
        if response:
            logger.info(
                f"Fetched personal account of login {response['login']} successfully"
            )
        return response

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

        - Optional: filter to allowed orgs + include personal account as pseudo-org
        """
        logger.info("Fetching organizations")

        allowed_multi_organizations: List[str] = options.get(
            "allowed_multi_organizations", []
        )
        include_authenticated_user: bool = options.get(
            "include_authenticated_user", False
        )

        if organization := options.get("organization"):
            logger.info(f"Fetching single organization {organization}")
            yield [
                await self.client.send_api_request(
                    f"{self.client.base_url}/users/{organization}"
                )
            ]
            return

        if not await self.is_classic_pat_token():
            raise OrganizationRequiredException(
                "Organization is required for non-classic PAT tokens"
            )

        async for batch in self._stream_selected_organizations(
            allowed_multi_organizations, include_authenticated_user
        ):
            yield batch

    async def get_resource[ExporterOptionsT: None](self, options: None) -> RAW_ITEM:
        raise NotImplementedError

    async def _stream_selected_organizations(
        self, allowed_multi_organizations: list[str], include_authenticated_user: bool
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        if include_authenticated_user:
            yield [await self.get_personal_org()]

        async for batch in self.client.send_paginated_request(
            f"{self.client.base_url}/user/orgs"
        ):
            yield [
                {**org, "type": "Organization"}
                for org in batch
                if not allowed_multi_organizations
                or org.get("login") in allowed_multi_organizations
            ]
