from loguru import logger

from port_ocean.utils.cache import cache_iterator_result, cache_coroutine_result
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from typing import Optional, cast

from integration import GithubPortAppConfig
from github.core.options import ListOrganizationOptions, SingleOrganizationOptions
from github.helpers.exceptions import AuthenticationException


class RestOrganizationExporter(AbstractGithubExporter[GithubRestClient]):
    """Exporter for GitHub organizations using REST API."""

    async def get_paginated_resources(
        self, options: ListOrganizationOptions | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch in self._get_paginated_resources(
            options, self.client.authenticator.rate_limit_scope
        ):
            yield batch

    @cache_iterator_result()
    async def _get_paginated_resources(
        self,
        options: ListOrganizationOptions | None,
        _auth_scope: str,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        If the authenticator or integration config scopes an organization, fetch it.
        Otherwise, fetch all organizations available to the authenticator,
        optionally filtering them and including the authenticated user.
        """
        port_app_config = cast(GithubPortAppConfig, event.port_app_config)
        allowed_multi_organizations = port_app_config.organizations
        include_authenticated_user = port_app_config.include_authenticated_user
        requested_organization = options.organization if options else None
        authenticated_organization = self.client.authenticator.organization

        if (
            requested_organization
            and authenticated_organization
            and requested_organization.casefold()
            != authenticated_organization.casefold()
        ):
            raise AuthenticationException(
                f"Authenticator for '{authenticated_organization}' cannot access "
                f"requested organization '{requested_organization}'"
            )

        if organization := (
            requested_organization
            or authenticated_organization
            or ocean.integration_config.get("github_organization")
        ):
            logger.info(f"Fetching single organization {organization}")
            organization_resource = await self.get_resource(
                SingleOrganizationOptions(organization=organization)
            )
            if organization_resource:
                yield [organization_resource]
            return

        async for batch in self._stream_selected_organizations(
            allowed_multi_organizations, include_authenticated_user, _auth_scope
        ):
            yield batch

    async def get_resource[ExporterOptionsT: SingleOrganizationOptions](
        self, options: SingleOrganizationOptions
    ) -> Optional[RAW_ITEM]:
        return await self.client.send_api_request(
            f"{self.client.base_url}/users/{options['organization']}"
        )

    async def _stream_selected_organizations(
        self,
        allowed_multi_organizations: list[str],
        include_authenticated_user: bool,
        auth_scope: str,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        if include_authenticated_user:
            yield [await self._get_personal_org(auth_scope)]

        async for batch in self.client.send_paginated_request(
            f"{self.client.base_url}/user/orgs"
        ):
            yield [
                {**org, "type": "Organization"}
                for org in batch
                if not allowed_multi_organizations
                or org.get("login") in allowed_multi_organizations
            ]

    @cache_coroutine_result()
    async def _get_personal_org(self, _auth_scope: str) -> RAW_ITEM:
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
