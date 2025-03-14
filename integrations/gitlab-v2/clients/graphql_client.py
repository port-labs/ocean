import asyncio
from typing import Any, AsyncIterator, Optional

from loguru import logger

from .base_client import HTTPBaseClient
from .queries import ProjectQueries


class GraphQLClient(HTTPBaseClient):
    RESOURCE_QUERIES = {
        "projects": ProjectQueries.LIST,
    }

    def __init__(self, base_url: str, token: str):
        super().__init__(f"{base_url}/api/graphql", token)

    async def get_resource(
        self, resource_type: str, variables: Optional[dict[str, Any]] = None
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
            Tuple of (nodes, nested_field_generators) where nodes is the resource list
            and nested_field_generators streams nested fields like labels.
        """
        query = self.RESOURCE_QUERIES.get(resource_type)
        async for nodes, generators in self._execute_paginated_query(
            query=str(query), resource_field=resource_type, variables=variables
        ):
            yield nodes, generators

    async def _execute_paginated_query(
        self,
        query: str,
        resource_field: str,
        variables: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[
        tuple[
            list[dict[str, Any]], list[AsyncIterator[tuple[str, list[dict[str, Any]]]]]
        ]
    ]:
        cursor = None

        while True:
            data = await self._execute_query(
                query,
                variables={"cursor": cursor, **(variables or {})},
            )

            resource_data = data.get(resource_field, {})
            nodes = resource_data.get("nodes", [])

            if not nodes:
                break

            nested_field_generators = [
                self._fetch_paginated_fields(node, query, variables or {})
                for node in nodes
            ]

            yield nodes, nested_field_generators

            page_info = resource_data.get("pageInfo", {})
            if not page_info.get("hasNextPage", False):
                break

            cursor = page_info.get("endCursor")

    async def _fetch_paginated_fields(
        self, resource: dict[str, Any], query: str, variables: dict[str, Any]
    ) -> AsyncIterator[tuple[str, list[dict[str, Any]]]]:
        field_generators = [
            self._paginate_field(resource, field, query, variables)
            for field, value in resource.items()
            if isinstance(value, dict) and "nodes" in value and "pageInfo" in value
        ]
        # Process generators directly without tasks
        for generator in field_generators:
            async for field_name, nodes in generator:
                yield field_name, nodes

    async def _paginate_field(
        self,
        parent: dict[str, Any],
        field_name: str,
        query: str,
        variables: dict[str, Any],
    ) -> AsyncIterator[tuple[str, list[dict[str, Any]]]]:
        field_data = parent.get(field_name, {})
        nodes = field_data.get("nodes", [])
        page_info = field_data.get("pageInfo", {})
        cursor = page_info.get("endCursor")
        logger.info(f"Initial {field_name} for {parent.get('id')}: {len(nodes)} nodes")
        yield field_name, nodes
        while page_info.get("hasNextPage", False):
            logger.debug(
                f"Fetching more '{field_name}' for {parent.get('id')} with cursor: {cursor}"
            )
            field_data_response = await self._execute_query(
                query,
                variables={f"{field_name}Cursor": cursor, **(variables or {})},
            )
            response_nodes = field_data_response.get("projects", {}).get("nodes", [])
            matching_parent = next(
                (p for p in response_nodes if p["id"] == parent["id"]), None
            )
            if not matching_parent:
                logger.warning(
                    f"No matching parent found for ID {parent.get('id', 'unknown')}"
                )
                break
            new_field_data = matching_parent.get(field_name, {})
            new_nodes = new_field_data.get("nodes", [])
            new_page_info = new_field_data.get("pageInfo", {})
            if not new_nodes:
                logger.warning(
                    f"No new {field_name} returned for {parent.get('id', 'unknown')}"
                )
                break
            logger.debug(
                f"Yielding {len(new_nodes)} new {field_name} nodes for {parent.get('id')}"
            )
            yield field_name, new_nodes
            cursor = new_page_info.get("endCursor")
            page_info = new_page_info

    async def _execute_query(
        self, query: str, variables: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        try:
            response = await self.send_api_request(
                "POST",
                "",
                data={
                    "query": query,
                    "variables": variables or {},
                },
            )

            if "errors" in response:
                logger.error(f"GraphQL query failed: {response['errors']}")
                raise Exception(f"GraphQL query failed: {response['errors']}")

            return response.get("data", {})
        except Exception as e:
            logger.error(f"Failed to execute GraphQL query: {str(e)}")
            raise
