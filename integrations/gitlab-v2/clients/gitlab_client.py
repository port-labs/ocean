from typing import Any, AsyncIterator

from loguru import logger

from .graphql_client import GraphQLClient
from .rest_client import RestClient


class GitLabClient:
    """Async client for interacting with GitLab API using both GraphQL and REST endpoints."""

    DEFAULT_MIN_ACCESS_LEVEL = 30

    def __init__(self, base_url: str, token: str) -> None:
        if not base_url or not token:
            raise ValueError("base_url and token must not be empty")

        self.graphql = GraphQLClient(base_url, token)
        self.rest = RestClient(base_url, token)

    async def get_projects(self) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch all accessible projects using GraphQL."""
        async for batch in self.graphql.get_resource("projects"):
            yield batch

    async def get_groups(self) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch all groups accessible to the user."""
        async for batch in self.rest.get_resource(
            "groups",
            params={
                "min_access_level": self.DEFAULT_MIN_ACCESS_LEVEL,
                "all_available": True,
            },
        ):
            yield batch

    async def get_group_resource(
        self, groups_batch: list[dict[str, Any]], resource_type: str
    ) -> AsyncIterator[list[dict[str, Any]]]:
        for group in groups_batch:
            group_id = group["id"]
            async for resource_batch in self.rest.get_group_resource(
                group_id, resource_type
            ):
                logger.info(f"Fetched {resource_type} batch for group {group['id']}")
                yield resource_batch
