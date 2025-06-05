from typing import cast
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SingleDeploymentOptions, ListDeploymentsOptions


class RestDeploymentExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleDeploymentOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        """Get a single deployment for a repository."""
        repo_name = options["repo_name"]
        id = options["id"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/deployments/{id}"
        response = await self.client.send_api_request(endpoint)

        logger.info(
            f"Fetched deployment with identifier: {id} from repository {repo_name}"
        )
        response["__repository"] = repo_name
        return response

    async def get_paginated_resources[
        ExporterOptionsT: ListDeploymentsOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all deployments for a repository with pagination."""

        params = dict(options)
        repo_name = cast(str, params.pop("repo_name"))

        async for deployments in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/deployments",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(deployments)} deployments from repository {repo_name}"
            )
            batch = [
                {**deployment, "__repository": repo_name} for deployment in deployments
            ]
            yield batch
