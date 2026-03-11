from typing import Optional
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleUserOptions, ListUserOptions
from github.helpers.gql_queries import (
    LIST_ORG_MEMBER_GQL,
    FETCH_GITHUB_USER_GQL,
)
from github.helpers.utils import enrich_members_with_saml_email


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
            await enrich_members_with_saml_email(self.client, organization, [user])
        return user

    async def get_paginated_resources[
        ExporterOptionT: ListUserOptions
    ](self, options: ExporterOptionT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        organization = options["organization"]
        variables = {
            "organization": organization,
            "__path": "organization.membersWithRole",
        }
        async for users in self.client.send_paginated_request(
            LIST_ORG_MEMBER_GQL, variables
        ):
            await enrich_members_with_saml_email(self.client, organization, users)
            yield users
