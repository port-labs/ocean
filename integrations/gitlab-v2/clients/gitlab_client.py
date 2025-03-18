from typing import Any, AsyncIterator
from loguru import logger

from .graphql_client import GraphQLClient
from .rest_client import RestClient


class GitLabClient:
    """Async client for interacting with GitLab API using both GraphQL and REST endpoints."""

    DEFAULT_MIN_ACCESS_LEVEL = 30

    def __init__(self, base_url: str, token: str) -> None:

        self.graphql = GraphQLClient(base_url, token, endpoint="api/graphql")
        self.rest = RestClient(base_url, token, endpoint="api/v4")

    async def get_projects(self) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch all accessible projects using GraphQL.
        Note: GraphQL is preferred over REST for projects as it allows efficient
        fetching of extendable fields (like members, labels, files) in a single query
        when needed, avoiding multiple API calls.
        """
        async for projects_batch, field_iterators in self.graphql.get_resource(
            "projects"
        ):
            if projects_batch:
                yield projects_batch

            async for updated_batch in self.graphql._process_nested_fields(
                projects_batch, field_iterators
            ):
                yield updated_batch

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
