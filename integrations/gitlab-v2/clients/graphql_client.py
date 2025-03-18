from typing import Any, AsyncIterator, Optional

from loguru import logger

from .base_client import HTTPBaseClient
from .queries import ProjectQueries
import asyncio
import gc

MAX_CONCURRENT_REQUESTS = 10


class GraphQLClient(HTTPBaseClient):
    BATCH_SIZE = 100  # Fetch batch
    SUB_BATCH_SIZE = 50  # Process sub-batch

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_REQUESTS)

    RESOURCE_QUERIES = {
        "projects": ProjectQueries.LIST,
    }

    async def get_resource(
        self, resource_type: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[
        tuple[
            list[dict[str, Any]], list[AsyncIterator[tuple[str, list[dict[str, Any]]]]]
        ]
    ]:
        """Fetch a paginated resource from the GraphQL API.

        Args:
            resource_type: Type of resource to fetch (e.g., 'projects').
            variables: Optional query variables (e.g., filters).

        Yields:
            tuple of (nodes, nested_field_generators) where nodes is the resource list
            and nested_field_generators streams nested fields like labels.
        """
        query = self.RESOURCE_QUERIES[resource_type]
        async for nodes, generators in self._execute_paginated_query(
            query=str(query), resource_field=resource_type, params=params
        ):
            yield nodes, generators

    async def _execute_paginated_query(
        self,
        query: str,
        resource_field: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[
        tuple[
            list[dict[str, Any]], list[AsyncIterator[tuple[str, list[dict[str, Any]]]]]
        ]
    ]:
        cursor = None

        while True:
            data = await self._execute_query(
                query,
                params={"cursor": cursor, **(params or {})},
            )

            resource_data = data[resource_field]
            nodes = resource_data.get("nodes", [])

            if not nodes:
                break

            nested_field_generators = [
                self._fetch_paginated_fields(
                    node, resource_field, query, variables or {}
                )
                for node in nodes
            ]

            yield nodes, nested_field_generators

            page_info = resource_data["pageInfo"]
            if not page_info["hasNextPage"]:
                break

            cursor = page_info.get("endCursor")

    async def _fetch_paginated_fields(
        self,
        resource: dict[str, Any],
        resource_field: str,
        query: str,
        variables: dict[str, Any],
    ) -> AsyncIterator[tuple[str, list[dict[str, Any]]]]:

        field_generators = [
            self._paginate_field(resource, field, resource_field, query, variables)
            for field, value in resource.items()
            if isinstance(value, dict) and "nodes" in value and "pageInfo" in value
        ]

        for generator in field_generators:
            async for field_name, nodes in generator:
                yield field_name, nodes

    async def _paginate_field(
        self,
        parent: dict[str, Any],
        field_name: str,
        resource_field: str,
        query: str,
        variables: dict[str, Any],
    ) -> AsyncIterator[tuple[str, list[dict[str, Any]]]]:
        """Stream paginated nodes for a field (e.g., labels) of a GitLab resource."""

        parent_id: str = parent["id"]
        field_data: dict[str, Any] = parent[field_name]
        nodes: list[dict[str, Any]] = field_data["nodes"]
        page_info: dict[str, Any] = field_data["pageInfo"]

        yield field_name, nodes

        cursor: str | None = page_info["endCursor"]
        while page_info["hasNextPage"]:
            if cursor is None:
                logger.error(
                    f"Missing cursor for {field_name} pagination on {parent_id}"
                )
                break

            logger.debug(f"Fetching '{field_name}' for {parent_id}")
            response = await self._execute_query(
                query,
                variables={f"{field_name}Cursor": cursor, **variables},
            )

            resource_nodes: list[dict[str, Any]] = response[resource_field]["nodes"]
            resource_field_data: dict[str, Any] = next(
                resource[field_name]
                for resource in resource_nodes
                if resource["id"] == parent_id
            )
            nodes = resource_field_data["nodes"]

            logger.info(f"Got {len(nodes)} {field_name} for {parent_id}")
            yield field_name, nodes

            page_info = resource_field_data["pageInfo"]
            cursor = page_info["endCursor"]

    async def safe_next(
        self, field_iter: AsyncIterator[tuple[str, list[dict[str, Any]]]]
    ) -> Optional[tuple[str, list[dict[str, Any]]]]:
        try:
            async with self._semaphore:
                return await anext(field_iter)
        except StopAsyncIteration:
            return None
        except Exception as e:
            logger.error(f"Error in iterator: {e}")
            return None

    async def _process_nested_fields(
        self,
        projects: list[dict[str, Any]],
        field_iterators: list[AsyncIterator[tuple[str, list[dict[str, Any]]]]],
    ) -> AsyncIterator[list[dict[str, Any]]]:
        active_data = list(zip(projects, field_iterators))  # 100 projects, paired with iterators
        while active_data:
            updated_projects = []  # Accumulate updated projects
            next_active = []
            # Process in two sub-batches of 50
            for start in range(0, min(len(active_data), self.BATCH_SIZE), self.SUB_BATCH_SIZE):
                sub_batch = active_data[start:start + self.SUB_BATCH_SIZE]  # 50 projects
                tasks = [self.safe_next(field_iter) for _, field_iter in sub_batch]
                results = await asyncio.gather(*tasks)
                for (project, field_iter), result in zip(sub_batch, results):
                    if result:
                        field_name, nodes = result
                        project[field_name]["nodes"].extend(nodes)  # GitLab provides structure
                        updated_projects.append(project)
                    next_active.append((project, field_iter))
            active_data = next_active
            if updated_projects:
                yield [self._copy_project(p) for p in projects]
                for project in projects:
                    project["labels"]["nodes"] = []
                gc.collect()  # Force cleanup


    def _copy_project(self, project: dict[str, Any]) -> dict[str, Any]:
        return {
            key: (
                {
                    "nodes": list(project[key]["nodes"]),
                    "pageInfo": project[key]["pageInfo"],
                }
                if key != "id"
                and isinstance(project[key], dict)
                and "nodes" in project[key]
                else project[key]
            )
            for key in project
        }

    async def _execute_query(
        self, query: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        try:
            response = await self.send_api_request(
                "POST",
                "",
                data={
                    "query": query,
                    "variables": params or {},
                },
            )

            if "errors" in response:
                logger.error(f"GraphQL query failed: {response['errors']}")
                raise Exception(f"GraphQL query failed: {response['errors']}")

            return response["data"]
        except Exception as e:
            logger.error(f"Failed to execute GraphQL query: {str(e)}")
            raise
