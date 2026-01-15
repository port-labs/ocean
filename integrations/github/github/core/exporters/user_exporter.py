import asyncio
from typing import Any
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleUserOptions, ListUserOptions
from github.helpers.gql_queries import (
    LIST_EXTERNAL_IDENTITIES_GQL,
    LIST_ORG_MEMBER_GQL,
    LIST_ORG_MEMBER_WITHOUT_BOTS_GQL,
    FETCH_GITHUB_USER_GQL,
)

SAML_LOAD_MAX_RETRIES = 3
SAML_LOAD_MAX_CONCURRENT = 3


class GraphQLUserExporter(AbstractGithubExporter[GithubGraphQLClient]):
    def __init__(self, client: GithubGraphQLClient) -> None:
        super().__init__(client)
        self._saml_identity_cache: dict[str, dict[str, str]] = {}

    async def get_resource[
        ExporterOptionT: SingleUserOptions
    ](self, options: ExporterOptionT) -> RAW_ITEM:
        organization = options["organization"]
        variables = {"login": options["login"]}
        payload = self.client.build_graphql_payload(FETCH_GITHUB_USER_GQL, variables)
        response = await self.client.send_api_request(
            self.client.base_url, method="POST", json_data=payload
        )
        if not response:
            return response

        user = response["data"]["user"]

        if not user.get("email"):
            await self._fetch_external_identities(
                organization, [user], {(0, user["login"]): user}
            )
        return user

    async def get_paginated_resources[
        ExporterOptionT: ListUserOptions
    ](self, options: ExporterOptionT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        variables = {
            "organization": options["organization"],
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
                    options["organization"], users, users_with_no_email
                )
            yield users

    async def _fetch_external_identities(
        self,
        organization: str,
        users: list[dict[str, Any]],
        users_no_email: dict[tuple[int, str], dict[str, Any]],
    ) -> None:
        remaining_users = set(users_no_email.keys())

        if organization not in self._saml_identity_cache:
            await self._load_saml_identities(organization)

        saml_users = self._saml_identity_cache.get(organization, {})

        for (idx, login), user in users_no_email.items():
            if login in saml_users:
                users[idx]["email"] = saml_users[login]
                remaining_users.remove((idx, login))

        if not remaining_users:
            logger.info(
                "Successfully retrieved and updated email addresses for all identified users from external identity provider."
            )

    async def preload_saml_identities_for_organizations(
        self,
        organizations: list[str],
    ) -> None:
        """Pre-load SAML identities for all organizations before user fetching.

        This prevents timeouts during user batch processing by loading all SAML
        identities upfront with controlled concurrency and rate limit handling.
        """
        if not organizations:
            return

        semaphore = asyncio.Semaphore(SAML_LOAD_MAX_CONCURRENT)

        async def load_with_limit(org: str) -> None:
            async with semaphore:
                if org not in self._saml_identity_cache:
                    await self._load_saml_identities(org)

        logger.info(
            f"Pre-loading SAML identities for {len(organizations)} organizations "
            f"(max concurrent: {SAML_LOAD_MAX_CONCURRENT})"
        )

        results = await asyncio.gather(
            *[load_with_limit(org) for org in organizations],
            return_exceptions=True,
        )

        # Log any failures
        for org, result in zip(organizations, results):
            if isinstance(result, Exception):
                logger.warning(
                    f"Failed to pre-load SAML identities for '{org}': {result}"
                )

        cached_count = len(self._saml_identity_cache)
        total_identities = sum(len(v) for v in self._saml_identity_cache.values())
        logger.info(
            f"SAML pre-load complete: {cached_count} organizations, "
            f"{total_identities} total identities cached"
        )

    async def _load_saml_identities(self, organization: str) -> None:
        """Load SAML identities for an organization with retry and backoff."""
        variables = {
            "organization": organization,
            "first": 100,
            "__path": "organization.samlIdentityProvider.externalIdentities",
            "__node_key": "edges",
        }

        saml_users: dict[str, str] = {}
        retry_count = 0
        page_count = 0

        while retry_count <= SAML_LOAD_MAX_RETRIES:
            try:
                async for identity_batch in self.client.send_paginated_request(
                    LIST_EXTERNAL_IDENTITIES_GQL,
                    variables,
                ):
                    page_count += 1
                    for user in identity_batch:
                        if user["node"].get("user"):
                            login = user["node"]["user"]["login"]
                            name_id = user["node"]["samlIdentity"]["nameId"]
                            saml_users[login] = name_id

                    # Log progress for large organizations
                    if page_count % 10 == 0:
                        logger.debug(
                            f"Loading SAML identities for '{organization}': "
                            f"{len(saml_users)} identities fetched ({page_count} pages)"
                        )

                self._saml_identity_cache[organization] = saml_users
                logger.info(
                    f"Cached {len(saml_users)} SAML identities for organization "
                    f"'{organization}' ({page_count} pages)"
                )
                return

            except TypeError:
                logger.info(f"SAML not enabled for organization '{organization}'")
                self._saml_identity_cache[organization] = {}
                return

            except Exception as e:
                retry_count += 1
                error_msg = str(e).lower()

                # Check if it's a rate limit or timeout error
                is_rate_limit = "rate" in error_msg or "limit" in error_msg
                is_timeout = "timeout" in error_msg or "timed out" in error_msg

                if retry_count <= SAML_LOAD_MAX_RETRIES and (is_rate_limit or is_timeout):
                    wait_time = 2 ** retry_count  # 2s, 4s, 8s
                    logger.warning(
                        f"{'Rate limited' if is_rate_limit else 'Timeout'} loading SAML "
                        f"for '{organization}', retry {retry_count}/{SAML_LOAD_MAX_RETRIES} "
                        f"in {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"Failed to load SAML identities for '{organization}' "
                        f"after {retry_count} attempts: {e}"
                    )
                    self._saml_identity_cache[organization] = {}
                    return

        # Exhausted retries
        logger.error(
            f"Exhausted retries loading SAML for '{organization}', proceeding without SAML data"
        )
        self._saml_identity_cache[organization] = {}
