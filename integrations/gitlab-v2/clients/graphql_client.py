from typing import Any, AsyncIterator, Optional

from loguru import logger

from .base_client import HTTPBaseClient
from .queries import ProjectQueries
import asyncio

MAX_CONCURRENT_REQUESTS = 10


class GraphQLClient(HTTPBaseClient):

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_REQUESTS)

    RESOURCE_QUERIES = {
        "projects": ProjectQueries.LIST,
        "project_labels": ProjectQueries.GET_LABELS,
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
                self._fetch_paginated_fields(node, resource_field, query, params or {})
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
        params: dict[str, Any],
    ) -> AsyncIterator[tuple[str, list[dict[str, Any]]]]:

        field_generators = [
            self._paginate_field(resource, field, resource_field, query, params)
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
        params: dict[str, Any],
    ) -> AsyncIterator[tuple[str, list[dict[str, Any]]]]:
        parent_id: str = parent["id"]  # Still used for logging
        parent_full_path: str = parent["fullPath"]  # Use fullPath for query
        field_data: dict[str, Any] = parent[field_name]
        nodes: list[dict[str, Any]] = field_data["nodes"]
        page_info: dict[str, Any] = field_data["pageInfo"]

        yield field_name, nodes  # Initial yield

        cursor: str | None = page_info["endCursor"]
        while page_info["hasNextPage"]:
            if cursor is None:
                logger.error(
                    f"Missing cursor for {field_name} pagination on {parent_id}"
                )
                break

            logger.debug(f"Fetching '{field_name}' for {parent_id}")
            label_query = self.RESOURCE_QUERIES["project_labels"]
            response = await self._execute_query(
                label_query,
                params={"fullPath": parent_full_path, "labelsCursor": cursor},
            )

            project_data = response["project"]
            if not project_data:
                logger.warning(
                    f"No project data returned for {parent_id} in {field_name} pagination"
                )
                break

            resource_field_data = project_data[field_name]
            nodes = resource_field_data["nodes"]

            if not nodes:
                logger.warning(
                    f"No more {field_name} found for {parent_id} at cursor {cursor}"
                )
                break

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
        active_data = list(zip(projects, field_iterators))
        while active_data:
            updated = False
            next_active = []
            tasks = [self.safe_next(field_iter) for _, field_iter in active_data]
            results = await asyncio.gather(*tasks)
            for (project, field_iter), result in zip(active_data, results):
                if result:
                    field_name, nodes = result
                    if nodes:
                        project[field_name]["nodes"].extend(nodes)
                        updated = True
                    next_active.append((project, field_iter))
            active_data = next_active
            if updated:
                yield [self._copy_project(project) for project, _ in active_data]
                project["labels"]["nodes"] = []

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
        for attempt in range(3):  # Retry up to 3 times
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
                logger.info(
                    f"Attempt {attempt+1}/3 failed to execute GraphQL query: {str(e)}"
                )
                if attempt < 2:  # Retry if not the last attempt
                    await asyncio.sleep(2**attempt)  # Backoff: 1, 2 sec
                else:
                    logger.error(f"All retries exhausted for GraphQL query: {str(e)}")
                    raise  # Raise on final failure
