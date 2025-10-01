from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import enrich_with_repository, extract_repo_params
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SingleDeploymentOptions, ListDeploymentsOptions


class RestDeploymentExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleDeploymentOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        """Get a single deployment for a repository."""
        repo_name, params = extract_repo_params(dict(options))
        id = params["id"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/deployments/{id}"
        response = await self.client.send_api_request(endpoint)

        logger.info(
            f"Fetched deployment with identifier {id} from repository {repo_name}"
        )

        return enrich_with_repository(response, repo_name)

    async def get_paginated_resources[
        ExporterOptionsT: ListDeploymentsOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all deployments for a repository with pagination."""

        repo_name, params = extract_repo_params(dict(options))

        async for deployments in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/deployments",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(deployments)} deployments from repository {repo_name}"
            )
            batch = [
                enrich_with_repository(deployment, repo_name)
                for deployment in deployments
            ]
            yield batch
