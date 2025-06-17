from typing import Any
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleUserOptions
from github.helpers.gql_queries import (
    LIST_EXTERNAL_IDENTITIES_GQL,
    LIST_ORG_MEMBER_GQL,
    FETCH_GITHUB_USER_GQL,
)


class GraphQLUserExporter(AbstractGithubExporter[GithubGraphQLClient]):
    async def get_resource[ExporterOptionT: SingleUserOptions](
        self, options: ExporterOptionT
    ) -> RAW_ITEM:
        variables = {"login": options["login"]}
        payload = self.client.build_graphql_payload(FETCH_GITHUB_USER_GQL, variables)
        res = await self.client.send_api_request(
            self.client.base_url, method="POST", json_data=payload
        )
        data = res.json()
        return data["data"]["user"]

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        variables = {
            "organization": self.client.organization,
            "__path": "organization.membersWithRole.nodes",
        }
        async for users in self.client.send_paginated_request(
            LIST_ORG_MEMBER_GQL, variables
        ):
            users_with_no_email = [
                user for user in enumerate(users) if not user[1].get("email")
            ]
            if users_with_no_email:
                await self._fetch_external_identities(users, users_with_no_email)
            yield users

    async def _fetch_external_identities(
        self,
        users: list[dict[str, Any]],
        users_no_email: list[tuple[int, dict[str, Any]]],
    ) -> None:
        variables = {
            "organization": self.client.organization,
            "first": 100,
            "__path": "organization.samlIdentityProvider.externalIdentities.edges",
        }
        num_users_remaining = len(users_no_email)
        async for identity_batch in self.client.send_paginated_request(
            LIST_EXTERNAL_IDENTITIES_GQL, variables
        ):
            saml_users: dict[str, Any] = {
                user["node"]["user"]["login"]: user
                for user in identity_batch
                if user["node"].get("user")
            }

            for idx, item in users_no_email:
                if saml_user := saml_users.get(item["login"]):
                    users[idx]["email"] = saml_user["node"]["samlIdentity"]["nameId"]
                    num_users_remaining -= 1

                if num_users_remaining < 1:
                    return
