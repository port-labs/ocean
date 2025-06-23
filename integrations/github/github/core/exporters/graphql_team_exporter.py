from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleTeamOptions
from github.helpers.gql_queries import (
    FETCH_TEAM_WITH_MEMBERS_GQL,
    LIST_TEAM_MEMBERS_GQL,
)


class GraphQLTeamExporter(AbstractGithubExporter[GithubGraphQLClient]):
    async def get_resource[
        ExporterOptionT: SingleTeamOptions
    ](self, options: ExporterOptionT) -> RAW_ITEM:
        variables = {"slug": options["slug"], "organization": self.client.organization}
        payload = self.client.build_graphql_payload(
            FETCH_TEAM_WITH_MEMBERS_GQL, variables
        )
        res = await self.client.send_api_request(
            self.client.base_url, method="POST", json_data=payload
        )
        data = res.json()
        return data["data"]["organization"]["team"]

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        variables = {
            "organization": self.client.organization,
            "__path": "organization.teams",
        }
        async for teams in self.client.send_paginated_request(
            LIST_TEAM_MEMBERS_GQL, variables
        ):
            yield teams
