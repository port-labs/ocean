from typing import cast, Optional
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import (
    enrich_with_repository,
    enrich_with_organization,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import (
    SingleDeploymentStatusOptions,
    ListDeploymentStatusesOptions,
)


class RestDeploymentStatusExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource(
        self, options: SingleDeploymentStatusOptions
    ) -> Optional[RAW_ITEM]:
        """Get a single deployment status for a deployment."""
        repo_name = options["repo_name"]
        organization = options["organization"]
        deployment_id = options["deployment_id"]
        status_id = options["status_id"]

        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/deployments/{deployment_id}/statuses/{status_id}"
        response = await self.client.send_api_request(endpoint)
        if not response:
            logger.warning(
                f"No deployment status found with id: {status_id} for deployment: {deployment_id} in repository: {repo_name} from {organization}"
            )
            return None

        logger.info(
            f"Fetched deployment status {status_id} for deployment {deployment_id} from repository {repo_name} from {organization}"
        )

        enriched = enrich_with_organization(
            enrich_with_repository(response, cast(str, repo_name)), organization
        )
        enriched["__deployment_id"] = deployment_id
        return enriched

    async def get_paginated_resources(
        self, options: ListDeploymentStatusesOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all deployment statuses for a deployment with pagination."""
        repo_name = options["repo_name"]
        organization = options["organization"]
        deployment_id = options["deployment_id"]

        async for statuses in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{organization}/{repo_name}/deployments/{deployment_id}/statuses",
        ):
            logger.info(
                f"Fetched batch of {len(statuses)} deployment statuses for deployment {deployment_id} from repository {repo_name} from {organization}"
            )
            batch = []
            for status in statuses:
                enriched = enrich_with_organization(
                    enrich_with_repository(status, cast(str, repo_name)),
                    organization,
                )
                enriched["__deployment_id"] = deployment_id
                batch.append(enriched)
            yield batch
