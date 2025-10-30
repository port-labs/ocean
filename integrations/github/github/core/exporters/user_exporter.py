from typing import Any
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleUserOptions, ListUserOptions
from github.helpers.utils import sanitize_login
from github.helpers.gql_queries import (
    LIST_EXTERNAL_IDENTITIES_GQL,
    LIST_ORG_MEMBER_GQL,
    FETCH_GITHUB_USER_GQL,
)


class GraphQLUserExporter(AbstractGithubExporter[GithubGraphQLClient]):
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
        user["login"] = sanitize_login(user["login"])

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
        async for users in self.client.send_paginated_request(
            LIST_ORG_MEMBER_GQL, variables
        ):
            if not options.get("include_bots"):
                users = [user for user in users if user.get("__typename") == "User"]

            # Sanitize login fields for all users
            users = [{**user, "login": sanitize_login(user["login"])} for user in users]

            users_with_no_email = {
                (idx, user["login"]): user
                for idx, user in enumerate(users)
                if not user.get("email") and user.get("__typename") == "User"
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
        variables = {
            "organization": organization,
            "first": 100,
            "__path": "organization.samlIdentityProvider.externalIdentities",
            "__node_key": "edges",
        }

        remaining_users = set(users_no_email.keys())

        try:
            async for identity_batch in self.client.send_paginated_request(
                LIST_EXTERNAL_IDENTITIES_GQL,
                variables,
            ):
                saml_users = {
                    sanitize_login(user["node"]["user"]["login"]): user["node"][
                        "samlIdentity"
                    ]["nameId"]
                    for user in identity_batch
                    if user["node"].get("user")
                }
                for (idx, login), user in users_no_email.items():
                    if login in saml_users:
                        users[idx]["email"] = saml_users[login]
                        remaining_users.remove((idx, login))

                if not remaining_users:
                    logger.info(
                        "Successfully retrieved and updated email addresses for all identified users from external identity provider."
                    )
                    return
        except TypeError:
            logger.info("SAML not enabled for organization")
            return
