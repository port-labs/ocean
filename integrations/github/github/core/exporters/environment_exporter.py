from typing import Any, cast
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import enrich_with_repository, extract_repo_params
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import ListEnvironmentsOptions, SingleEnvironmentOptions


class RestEnvironmentExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[
        ExporterOptionsT: SingleEnvironmentOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        """Get a single environment for a repository."""

        repo_name, params = extract_repo_params(dict(options))
        name = params["name"]

        endpoint = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/environments/{name}"
        response = await self.client.send_api_request(endpoint)

        logger.info(
            f"Fetched environment with identifier {name} from repository {repo_name}"
        )

        return enrich_with_repository(response, repo_name)

    async def get_paginated_resources[
        ExporterOptionsT: ListEnvironmentsOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all environments for a repository with pagination."""

        repo_name, params = extract_repo_params(dict(options))

        async for response in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/environments",
            params,
        ):
            typed_response = cast(dict[str, Any], response)
            environments: list[dict[str, Any]] = typed_response["environments"]

            logger.info(
                f"Fetched batch of {len(environments)} environments from repository {repo_name}"
            )
            batch = [
                enrich_with_repository(environment, repo_name)
                for environment in environments
            ]
            yield batch
