import asyncio
from typing import Any, cast
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.helpers.utils import enrich_with_repository, parse_github_options
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import ListEnvironmentsOptions, SingleEnvironmentOptions


class RestEnvironmentExporter(AbstractGithubExporter[GithubRestClient]):
    async def _enrich_with_variables(
        self,
        repo_name: str,
        env_name: str,
        organization: str,
        environment: dict[str, Any],
    ) -> dict[str, Any]:
        """Fetch all variables for an environment and attach them as __variables."""
        variables: list[dict[str, Any]] = []
        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/environments/{env_name}/variables"

        async for response in self.client.send_paginated_request(endpoint):
            typed_response = cast(dict[str, Any], response)
            variables.extend(typed_response.get("variables", []))

        logger.debug(
            f"Fetched {len(variables)} variables for environment '{env_name}' in '{repo_name}'"
        )
        return {**environment, "__variables": variables}

    async def get_resource[
        ExporterOptionsT: SingleEnvironmentOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        """Get a single environment for a repository."""

        repo_name, organization, params = parse_github_options(dict(options))
        name = params["name"]
        include_variables = bool(params.get("variables", False))

        endpoint = f"{self.client.base_url}/repos/{organization}/{repo_name}/environments/{name}"
        response = await self.client.send_api_request(endpoint)

        if include_variables:
            response = await self._enrich_with_variables(
                cast(str, repo_name), name, cast(str, organization), response
            )

        logger.info(
            f"Fetched environment with identifier {name} from repository {repo_name} from {organization}"
        )

        return enrich_with_repository(response, cast(str, repo_name))

    async def get_paginated_resources[
        ExporterOptionsT: ListEnvironmentsOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all environments for a repository with pagination."""

        repo_name, organization, params = parse_github_options(dict(options))
        include_variables = bool(params.pop("variables", False))

        async for response in self.client.send_paginated_request(
            f"{self.client.base_url}/repos/{organization}/{repo_name}/environments",
            params,
        ):
            typed_response = cast(dict[str, Any], response)
            environments: list[dict[str, Any]] = typed_response["environments"]

            logger.info(
                f"Fetched batch of {len(environments)} environments from repository {repo_name} from {organization}"
            )

            if include_variables:
                tasks = [
                    self._enrich_with_variables(
                        cast(str, repo_name), env["name"], cast(str, organization), env
                    )
                    for env in environments
                ]
                environments = list(await asyncio.gather(*tasks))

            batch = [
                enrich_with_repository(environment, cast(str, repo_name))
                for environment in environments
            ]
            yield batch
