from typing import Any, Optional
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_coroutine_result
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleUserOptions, ListUserOptions
from github.helpers.gql_queries import (
    LIST_EXTERNAL_IDENTITIES_GQL,
    LIST_ORG_MEMBER_GQL,
    LIST_ORG_MEMBER_WITHOUT_BOTS_GQL,
    FETCH_GITHUB_USER_GQL,
)


class GraphQLUserExporter(AbstractGithubExporter[GithubGraphQLClient]):
    async def get_resource[
        ExporterOptionT: SingleUserOptions
    ](self, options: ExporterOptionT) -> Optional[RAW_ITEM]:
        organization = options["organization"]
        login_option = options["login"]
        variables = {"login": login_option}
        payload = self.client.build_graphql_payload(FETCH_GITHUB_USER_GQL, variables)
        response = await self.client.send_api_request(
            self.client.base_url, method="POST", json_data=payload
        )
        if not response:
            logger.warning(f"No user found with login: {login_option}")
            return None

        user = response["data"]["user"]

        if not user.get("email"):
            await self._fetch_external_identities(
                organization, [user], {(0, user["login"]): user}
            )
        return user

    async def get_paginated_resources[
        ExporterOptionT: ListUserOptions
    ](self, options: ExporterOptionT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        organization = options["organization"]
        variables = {
            "organization": organization,
            "__path": "organization.membersWithRole",
        }
        include_bots = options.get("include_bots")
        if include_bots:
            resource = LIST_ORG_MEMBER_GQL
        else:
            resource = LIST_ORG_MEMBER_WITHOUT_BOTS_GQL
        async for users in self.client.send_paginated_request(resource, variables):
            users_with_no_email = {
                (idx, user["login"]): user
                for idx, user in enumerate(users)
                if not user.get("email")
            }

            if users_with_no_email:
                logger.info(
                    f"Found {len(users_with_no_email)} users without an email address."
                    f"Attempting to fetch their emails from an external identity provider."
                )
                await self._fetch_external_identities(
                    organization, users, users_with_no_email
                )
            yield users

    async def _fetch_external_identities(
        self,
        organization: str,
        users: list[dict[str, Any]],
        users_no_email: dict[tuple[int, str], dict[str, Any]],
    ) -> None:
        remaining_users = set(users_no_email.keys())

        saml_users = await self._get_saml_identities(organization)

        for (idx, login), user in users_no_email.items():
            if login in saml_users:
                users[idx]["email"] = saml_users[login]
                remaining_users.remove((idx, login))

        if not remaining_users:
            logger.info(
                "Successfully retrieved and updated email addresses for all identified users from external identity provider."
            )

    @cache_coroutine_result()
    async def _get_saml_identities(self, organization: str) -> dict[str, str]:
        """Load and cache SAML identities for an organization.

        Uses Ocean's built-in caching to prevent redundant API calls across batches.
        """
        variables = {
            "organization": organization,
            "first": 100,
            "__path": "organization.samlIdentityProvider.externalIdentities",
            "__node_key": "edges",
        }

        saml_users: dict[str, str] = {}
        batch_count = 0

        logger.info(f"Starting SAML identity fetch for organization '{organization}'")

        try:
            async for identity_batch in self.client.send_paginated_request(
                LIST_EXTERNAL_IDENTITIES_GQL,
                variables,
            ):
                for user in identity_batch:
                    if user["node"].get("user"):
                        login = user["node"]["user"]["login"]
                        name_id = user["node"]["samlIdentity"]["nameId"]
                        saml_users[login] = name_id

            logger.info(
                f"SAML fetch complete for '{organization}': "
                f"{len(saml_users)} identities in {batch_count} batches"
            )
        except TypeError:
            logger.info(f"SAML not enabled for organization '{organization}'")
        return saml_users
