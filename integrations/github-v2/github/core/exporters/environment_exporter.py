from typing import Any, Dict
from github.clients.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.base_client import AbstractGithubClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import ListEnvironmentsOptions, SingleEnvironmentOptions


class RestEnvironmentExporter(AbstractGithubExporter[GithubRestClient]):
    """REST exporter for GitHub environments."""

    def get_required_client(self) -> type[AbstractGithubClient]:
        return GithubRestClient

    async def get_resource(self, options: SingleEnvironmentOptions) -> RAW_ITEM:
        """Get a single environment for a repository."""
        repo_name = options["repo_name"]
        name = options["name"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/environments/{name}"
        response = await self.client.send_api_request(endpoint)

        logger.info(f"Fetched environment with identifier: {name} from repository {repo_name}")
        return response.json()

    async def get_paginated_resources(
        self, options: ListEnvironmentsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all environments for a repository with pagination."""
        repo_name = options["repo_name"]
        params: Dict[str, Any] = dict(options) if options else {}
        params.pop("repo_name")

        async for response in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/environments",
            params
        ):
            print("response", response)
            environments = response["environments"]
            
            logger.info(
                f"Fetched batch of {len(environments)} environments from repository {repo_name}"
            )
            yield environments 