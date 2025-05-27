from typing import override

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleTeamOptions


class RestTeamExporter(AbstractGithubExporter[GithubRestClient]):
    @override
    async def get_resource[
        ExporterOptionT: SingleTeamOptions
    ](self, options: ExporterOptionT) -> RAW_ITEM:
        url = f"{self.client.base_url}/orgs/{self.client.organization}/teams/{options['slug']}"
        res = await self.client.send_api_request(url)
        data = res.json()
        return data

    @override
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        url = f"{self.client.base_url}/orgs/{self.client.organization}/teams"
        async for teams in self.client.send_paginated_request(url):
            yield teams
