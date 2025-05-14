from github.core.exporters.abstract_exporter import AbstractGithubExporter
from typing import Any, TYPE_CHECKING
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.clients.base_client import AbstractGithubClient

if TYPE_CHECKING:
    from integration import GithubRepositorySelector


class RepositoryExporter(AbstractGithubExporter[AbstractGithubClient]):

    async def get_resource(self, resource_id: str) -> dict[str, Any]:
        endpoint = f"orgs/{self.client.organization}/repos/{resource_id}"
        response = await self.client.send_api_request(endpoint)
        logger.debug(f"Fetched repository with identifier: {resource_id}:")
        return response.json()

    @cache_iterator_result()
    async def get_paginated_resources(
        self, selector: "GithubRepositorySelector"
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all repositories in the organization with pagination."""

        params = {"type": selector.type}
        async for repos in self.client.send_paginated_request(
            f"orgs/{self.client.organization}/repos", params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from organization {self.client.organization}"
            )
            yield repos
