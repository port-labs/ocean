from github.core.exporters.abstract_exporter import (
    AbstractGithubExporter,
    AbstractGithubExporterOptions,
)
from typing import Any, cast
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.clients.base_client import AbstractGithubClient


class RepositoryExporterOptions(AbstractGithubExporterOptions):
    type: str


class RepositoryExporter(AbstractGithubExporter[AbstractGithubClient]):

    async def get_resource(self, resource_id: str) -> dict[str, Any]:
        endpoint = f"repos/{self.client.organization}/{resource_id}"
        response = await self.client.send_api_request(endpoint)

        logger.debug(f"Fetched repository with identifier: {resource_id}")

        return response.json()

    @cache_iterator_result()
    async def get_paginated_resources(
        self,
        options: RepositoryExporterOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all repositories in the organization with pagination."""

        params = cast(dict[str, Any], options)

        async for repos in self.client.send_paginated_request(
            f"orgs/{self.client.organization}/repos", params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from organization {self.client.organization}"
            )
            yield repos
