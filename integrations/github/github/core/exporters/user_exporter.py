from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleUserOptions
from github.helpers.constants import LIST_ORG_MEMBER_GQL


class GraphQLUserExporter(AbstractGithubExporter[GithubGraphQLClient]):
    async def get_resource[
        ExporterOptionT: SingleUserOptions
    ](self, options: ExporterOptionT) -> RAW_ITEM:
        query = """
        query ($login: String!) {
            user(login: $login) {
                login
                email
            }
        }
        """
        variables = {"login": options["login"]}
        payload = {"query": query, "variables": variables}
        res = await self.client.send_api_request(
            query, method="POST", json_data=payload
        )
        data = res.json()
        return data["data"]["user"]

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        variables = {
            "organization": self.client.organization,
            "__path": "organization.membersWithRole",
        }
        async for users in self.client.send_paginated_request(
            LIST_ORG_MEMBER_GQL, variables
        ):
            yield users
