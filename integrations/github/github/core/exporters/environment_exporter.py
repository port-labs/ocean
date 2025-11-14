from typing import Any, cast
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import (
    enrich_with_repository,
    parse_github_options,
    enrich_with_organization,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import ListEnvironmentsOptions, SingleEnvironmentOptions


class RestEnvironmentExporter(AbstractGithubExporter[GithubRestClient]):
    async def get_resource[
        ExporterOptionsT: SingleEnvironmentOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        """Get a single environment for a repository."""

        repo_name, organization, params = parse_github_options(dict(options))
        name = params["name"]

        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/environments/{name}"
        response = await self.client.send_api_request(endpoint)

        logger.info(
            f"Fetched environment with identifier {name} from repository {repo_name} from {organization}"
        )

        return enrich_with_organization(
            enrich_with_repository(response, cast(str, repo_name)), organization
        )

    async def get_paginated_resources[
        ExporterOptionsT: ListEnvironmentsOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all environments for a repository with pagination."""

        repo_name, organization, params = parse_github_options(dict(options))

        async for response in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{organization}/{repo_name}/environments",
            params,
        ):
            typed_response = cast(dict[str, Any], response)
            environments: list[dict[str, Any]] = typed_response["environments"]

            logger.info(
                f"Fetched batch of {len(environments)} environments from repository {repo_name} from {organization}"
            )
            batch = [
                enrich_with_organization(
                    enrich_with_repository(environment, cast(str, repo_name)),
                    organization,
                )
                for environment in environments
            ]
            yield batch
