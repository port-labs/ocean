from typing import Any, AsyncIterator
import asyncio
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
        """Fetch all accessible projects using GraphQL.
        Note: GraphQL is preferred over REST for projects as it allows efficient
        fetching of extendable fields (like members, labels) in a single query
        when needed, avoiding multiple API calls.
        """
        async for projects_batch, field_iterators in self.graphql.get_resource(
            "projects"
        ):
            if projects_batch:
                yield projects_batch

            async for updated_batch in self._process_nested_fields(
                projects_batch, field_iterators
            ):
                yield updated_batch

    async def _process_nested_fields(
        self,
        projects: list[dict[str, Any]],
        field_iterators: list[AsyncIterator[tuple[str, list[dict[str, Any]]]]],
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Process nested fields for a batch of projects, yielding after meaningful updates."""
        project_field_nodes: list[dict[str, list[dict[str, Any]]]] = [
            {} for _ in projects
        ]
        active_data = list(zip(projects, field_iterators, project_field_nodes))

        while active_data:
            updated = False
            next_active: list[
                tuple[
                    dict[str, Any],
                    AsyncIterator[tuple[str, list[dict[str, Any]]]],
                    dict[str, list[dict[str, Any]]],
                ]
            ] = []

            for project, field_iter, field_nodes in active_data:
                try:
                    field_name, nodes = await anext(field_iter)
                    if nodes:
                        # Initialize or extend field nodes collection
                        if field_name not in field_nodes:
                            field_nodes[field_name] = []
                        field_nodes[field_name].extend(nodes)
                        project[field_name]["nodes"] = field_nodes[field_name]
                        updated = True

                    next_active.append((project, field_iter, field_nodes))
                except StopAsyncIteration:
                    pass

            active_data = next_active

            if updated:
                logger.info(f"Yielding batch with {len(projects)} projects")
                yield projects

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
