from typing import Any, Dict
from github.clients.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.base_client import AbstractGithubClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SingleDeploymentOptions, ListDeploymentsOptions


class RestDeploymentExporter(AbstractGithubExporter[GithubRestClient]):
    """REST exporter for GitHub deployments."""

    def get_required_client(self) -> type[AbstractGithubClient]:
        return GithubRestClient

    async def get_resource(self, options: SingleDeploymentOptions) -> RAW_ITEM:
        """Get a single deployment for a repository."""
        repo_name = options["repo_name"]
        id = options["id"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/deployments/{id}"
        response = await self.client.send_api_request(endpoint)

        logger.info(
            f"Fetched deployment with identifier: {id} from repository {repo_name}"
        )
        return response.json()

    async def get_paginated_resources(
        self, options: ListDeploymentsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all deployments for a repository with pagination."""
        repo_name = options["repo_name"]
        params: Dict[str, Any] = dict(options) if options else {}
        params.pop("repo_name")

        async for deployments in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/deployments",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(deployments)} deployments from repository {repo_name}"
            )
            yield deployments
