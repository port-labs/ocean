from typing import List, Optional

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result, cache_coroutine_result

from github.clients.http.rest_client import GithubRestClient
from github.clients.utils import get_github_organizations
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListOrganizationOptions


class RestOrganizationExporter(AbstractGithubExporter[GithubRestClient]):
    """Exporter for GitHub organizations using REST API."""

    @cache_coroutine_result()
    async def get_personal_org(self) -> RAW_ITEM:
        """Fetch the personal account of the authenticated user."""
        logger.info("Fetching personal account")
        response = await self.client.send_api_request(f"{self.client.base_url}/user")
        if response:
            logger.info(
                f"Fetched personal account of login {response['login']} successfully"
            )
        return response

    @cache_iterator_result()
    async def get_paginated_resources(
        self,
        options: ListOrganizationOptions | None = None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Discover organizations for this client's credentials.

        GitHub App installations yield the installed organization. Personal
        access tokens page ``/user/orgs``, optionally including the token
        owner's personal account, or fetch a single org when ``organization``
        is set in ``options``, on the authenticator, or in integration config.

        Omit ``options`` to apply listing defaults from the port app config.
        """
        logger.info("Fetching organizations")

        resolved_options = get_github_organizations() if options is None else options

        allowed_multi_organizations: List[str] = resolved_options.get(
            "allowed_multi_organizations", []
        )
        include_authenticated_user: bool = resolved_options.get(
            "include_authenticated_user", False
        )

        organization = resolved_options.get("organization")
        if organization:
            if (
                allowed_multi_organizations
                and organization not in allowed_multi_organizations
            ):
                return

            logger.info(f"Fetching single organization {organization}")
            yield [
                await self.client.send_api_request(
                    f"{self.client.base_url}/users/{organization}"
                )
            ]
            return

        async for batch in self._stream_selected_organizations(
            allowed_multi_organizations, include_authenticated_user
        ):
            yield batch

    async def get_resource[ExporterOptionsT: None](
        self, options: None
    ) -> Optional[RAW_ITEM]:
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
