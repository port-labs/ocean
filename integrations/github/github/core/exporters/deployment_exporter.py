from typing import cast
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import (
    enrich_with_repository,
    parse_github_options,
    enrich_with_organization,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import SingleDeploymentOptions, ListDeploymentsOptions


class RestDeploymentExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: SingleDeploymentOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        """Get a single deployment for a repository."""
        repo_name, organization, params = parse_github_options(dict(options))
        deployment_id = params["id"]

        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/deployments/{deployment_id}"
        response = await self.client.send_api_request(endpoint)

        logger.info(
            f"Fetched deployment with identifier {deployment_id} from repository {repo_name} from {organization}"
        )

        return enrich_with_organization(
            enrich_with_repository(response, cast(str, repo_name)), organization
        )

    async def get_paginated_resources[
        ExporterOptionsT: ListDeploymentsOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all deployments for a repository with pagination."""

        repo_name, organization, params = parse_github_options(dict(options))

        async for deployments in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{organization}/{repo_name}/deployments",
            params,
        ):
            logger.info(
                f"Fetched batch of {len(deployments)} deployments from repository {repo_name} from {organization}"
            )
            batch = [
                enrich_with_organization(
                    enrich_with_repository(deployment, cast(str, repo_name)),
                    organization,
                )
                for deployment in deployments
            ]
            yield batch
