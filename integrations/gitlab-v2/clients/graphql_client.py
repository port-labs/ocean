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
        self, resource_type: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        query = self.RESOURCE_QUERIES.get(resource_type)
        if not query:
            raise ValueError(f"Unsupported resource type for GraphQL: {resource_type}")

        async for batch in self._execute_paginated_query(
            query=str(query), resource_field=resource_type, params=params
        ):
            yield batch

    async def _execute_paginated_query(
        self,
        query: str,
        resource_field: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:

        cursor = None

        while True:
            data = await self._execute_query(
                query,
                params={"cursor": cursor, **(params or {})},
            )

            resource_data = data.get(resource_field, {})
            nodes = resource_data.get("nodes", [])

            if not nodes:
                break

            # Concurrently paginate paginated fields (e.g., labels, members, etc)
            await asyncio.gather(
                *(
                    self._fetch_paginated_fields(node, query, variables or {})
                    for node in nodes
                )
            )

            yield nodes

            # Check if there are more pages
            page_info = resource_data.get("pageInfo", {})
            if not page_info.get("hasNextPage", False):
                break

            cursor = page_info.get("endCursor")

    async def _fetch_paginated_fields(
        self, resource: dict[str, Any], query: str, variables: dict[str, Any]
    ) -> Any:
        tasks = [
            self._paginate_field(resource, field, query, variables)
            for field, value in resource.items()
            if isinstance(value, dict) and "nodes" in value and "pageInfo" in value
        ]

        await asyncio.gather(*tasks)

    async def _paginate_field(
        self,
        parent: dict[str, Any],
        field_name: str,
        query: str,
        variables: dict[str, Any],
    ) -> None:
        field_data = parent.get(field_name, {})
        nodes = field_data.get("nodes", [])
        page_info = field_data.get("pageInfo", {})

        cursor = page_info.get("endCursor")

        while page_info.get("hasNextPage", False):
            logger.info(
                f"Fetching more '{field_name}' for {parent.get('id', 'unknown')} with cursor: {cursor}"
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
                    f"No new {field_name} returned for {parent.get('id', 'unknown')}, stopping pagination."
                )
                break

            nodes.extend(new_nodes)
            cursor = new_page_info.get("endCursor")
            page_info = new_page_info

            if not cursor:
                logger.warning(
                    f"Cursor is None for {parent.get('id', 'unknown')}, stopping pagination."
                )
                break

        parent[field_name]["nodes"] = nodes

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

            return response.get("data", {})
        except Exception as e:
            logger.error(f"Failed to execute GraphQL query: {str(e)}")
            raise
