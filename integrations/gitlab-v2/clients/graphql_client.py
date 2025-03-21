from typing import Any, AsyncIterator, Optional

from loguru import logger

from .base_client import HTTPBaseClient
from .queries import ProjectQueries
import asyncio
import gc
from tenacity import retry, stop_after_attempt, wait_exponential
from .exceptions import GraphQLQueryError


MAX_CONCURRENT_REQUESTS = 10


class GraphQLClient(HTTPBaseClient):

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_REQUESTS)

    RESOURCE_QUERIES = {
        "projects": ProjectQueries.LIST,
        "labels": ProjectQueries.GET_LABELS,
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
        """Execute a paginated GraphQL query to fetch resources and their nested field iterators.

        This method paginates through a resource (e.g., projects) using the provided GraphQL query,
        yielding batches of resource nodes along with iterators for their nested fields (e.g., labels).

        Args:
            query (str): The GraphQL query string to execute (e.g., `ProjectQueries.LIST`).
            resource_field (str): The field in the query response containing the resource data
                (e.g., "projects").
            params (Optional[dict[str, Any]]): Additional query parameters (e.g., filters).
                Defaults to None.

        Yields:
            tuple[list[dict[str, Any]], list[AsyncIterator[tuple[str, list[dict[str, Any]]]]]]:
                A tuple containing:
                - A list of resource nodes (e.g., list of project dictionaries).
                - A list of async iterators for nested fields (e.g., label iterators for each project).
        """
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
                self._fetch_paginated_fields(node, params or {}) for node in nodes
            ]

            yield nodes, nested_field_generators

            page_info = resource_data["pageInfo"]
            if not page_info["hasNextPage"]:
                break

            cursor = page_info.get("endCursor")

    async def _fetch_paginated_fields(
        self,
        resource: dict[str, Any],
        params: dict[str, Any],
    ) -> AsyncIterator[tuple[str, list[dict[str, Any]]]]:
        """Fetch paginated nested fields for a resource.

        This method iterates over the nested fields of a resource (e.g., labels of a project)
        that have pagination data (`nodes` and `pageInfo`), creating async iterators for each
        field and yielding their paginated data.

        Args:
            resource (dict[str, Any]): The resource dictionary containing nested fields
                (e.g., a project with a "labels" field).
            params (dict[str, Any]): Query parameters to pass to the field pagination
                (e.g., filters).

        Yields:
            tuple[str, list[dict[str, Any]]]: A tuple containing:
                - The field name (e.g., "labels").
                - A list of nodes for that field (e.g., list of label dictionaries).

        Raises:
            Exception: If the underlying `_paginate_field` or `_execute_query` fails.
        """

        field_generators = [
            self._paginate_field(resource, field, params)
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
        params: dict[str, Any],
    ) -> AsyncIterator[tuple[str, list[dict[str, Any]]]]:
        """Paginate a nested field for a specific resource.

        This method paginates a nested field (e.g., labels) for a given resource (e.g., a project),
        yielding batches of nodes as they are fetched from the GraphQL API. It uses a field-specific
        query (e.g., `LabelQueries.GET_LABELS`) to fetch additional pages of data.

        Args:
            parent (dict[str, Any]): The parent resource dictionary (e.g., a project).
            field_name (str): The name of the field to paginate (e.g., "labels").
            params (dict[str, Any]): Additional query parameters (e.g., filters).

        Yields:
            tuple[str, list[dict[str, Any]]]: A tuple containing:
                - The field name (e.g., "labels").
                - A list of nodes for that field (e.g., list of label dictionaries).
        """

        parent_id: str = parent["id"]
        parent_full_path: str = parent["fullPath"]
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
            resource_query = self.RESOURCE_QUERIES[field_name]
            response = await self._execute_query(
                resource_query,
                params={
                    "fullPath": parent_full_path,
                    "labelsCursor": cursor,
                    **(params or {}),
                },
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
        """Process nested fields for a batch of projects, yielding updated project data.

        This method processes nested fields (e.g., labels) for a batch of projects in parallel,
        fetching paginated data from the provided iterators and updating the projects' nested
        field nodes. It yields the updated projects whenever new data is added, clearing the
        accumulated nodes to manage memory usage.

        Args:
            projects (list[dict[str, Any]]): List of project dictionaries to process.
            field_iterators (list[AsyncIterator[tuple[str, list[dict[str, Any]]]]]): List of
                async iterators for the nested fields of each project (e.g., label iterators).

        Yields:
            list[dict[str, Any]]: A list of updated project dictionaries with their nested
                field nodes (e.g., labels) appended.

        Notes:
            - Clears `project[field_name]["nodes"]` after each yield to minimize memory usage.
            - Processes all iterators in parallel using `asyncio.gather`.
        """
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
                for project, _ in active_data:
                    project[field_name]["nodes"] = []
                gc.collect()  # Force garbage collection

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

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def _execute_query(
        self, query: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        response = await self.send_api_request(
            "POST", "", data={"query": query, "variables": params or {}}
        )
        if "errors" in response:
            logger.error(f"GraphQL query failed: {response['errors']}")
            raise GraphQLQueryError(
                f"GraphQL query failed: {response['errors']}", response["errors"]
            )

        return response["data"]
