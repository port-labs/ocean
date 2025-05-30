from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleUserOptions
from github.helpers.gql_queries import LIST_ORG_MEMBER_GQL, FETCH_GITHUB_USER_GQL


class GraphQLUserExporter(AbstractGithubExporter[GithubGraphQLClient]):
    async def get_resource[
        ExporterOptionT: SingleUserOptions
    ](self, options: ExporterOptionT) -> RAW_ITEM:
        variables = {"login": options["login"]}
        payload = {"query": FETCH_GITHUB_USER_GQL, "variables": variables}
        res = await self.client.send_api_request(
            FETCH_GITHUB_USER_GQL, method="POST", json_data=payload
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
