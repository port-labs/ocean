import asyncio
from typing import Any, AsyncIterator

from loguru import logger

from .graphql_client import GraphQLClient
from .rest_client import RestClient


class GitLabClient:
    MAX_CONCURRENT_REQUESTS = 10

    def __init__(self, base_url: str, token: str) -> None:
        self.graphql = GraphQLClient(base_url, token)
        self.rest = RestClient(base_url, token)

    async def get_projects(self) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch all accessible projects using GraphQL."""
        async for batch in self.graphql.get_resource("projects"):
            yield batch

    async def get_groups(self) -> AsyncIterator[list[dict[str, Any]]]:
        async for batch in self.rest.get_resource(
            "groups", params={"min_access_level": 30, "all_available": True}
        ):
            yield batch

    async def get_group_resource(
        self, group: dict[str, Any], resource_type: str
    ) -> AsyncIterator[list[dict[str, Any]]]:
        async for batch in self.rest.get_group_resource(group["id"], resource_type):
            yield batch

    async def _fetch_resources_for_group(
        self, group: dict[str, Any], resource_type: str
    ) -> list[list[dict[str, Any]]]:
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
        async with semaphore:
            resources = []
            async for resource_batch in self.get_group_resource(group, resource_type):
                logger.info(
                    f"Received {resource_type} batch with {len(resource_batch)} items for group {group['id']}"
                )
                resources.append(resource_batch)
            return resources

    async def process_group_resources(
        self, groups_batch: list[dict[str, Any]], resource_type: str
    ) -> AsyncIterator[list[dict[str, Any]]]:
        tasks = [
            self._fetch_resources_for_group(group, resource_type)
            for group in groups_batch
        ]
        results = await asyncio.gather(*tasks)

        for group_result in results:
            for resource_batch in group_result:
                yield resource_batch
