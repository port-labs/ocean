from github.core.exporters.abstract_exporter import AbstractGithubExporter
from typing import Any, TYPE_CHECKING, cast
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger
from github.clients.base_client import AbstractGithubClient

if TYPE_CHECKING:
    from integration import GithubRepositorySelector


class WorkflowExporter(AbstractGithubExporter[AbstractGithubClient]):
    async def get_resource(self, resource_id: str) -> dict[str, Any]:
        endpoint = f"repos/{self.client.organization}/{resource_id}"
        response = await self.client.send_api_request(endpoint)

        logger.debug(f"Fetched repository with identifier: {resource_id}")

        return response.json()

    @cache_iterator_result()
    async def get_paginated_resources(
        self, selector: "GithubRepositorySelector"
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all repositories in the organization with pagination."""

        params = {"type": selector.type}
        url = f"repos/{self.client.organization}/{repo}/actions/workflows"
        async for workflows in self.client.send_paginated_request(url, params):
            # Unlike almost everywhere else, the result returned by workflows is not actually an array
            # So let's do some type casting here rather than force every other method to handle a rare case
            workflow_batch = cast(dict[str, Any | list[dict[str, Any]]], workflows)
            logger.info(
                f"fetched batch of {workflow_batch['total_count']} from repository - {repo}"
            )
            yield workflow_batch["workflows"]
