from typing import AsyncIterator, Optional, Any
from loguru import logger
from .auth_client import AuthClient
from .queries import ProjectQueries
from port_ocean.utils import http_async_client


class GraphQLClient:
    RESOURCE_QUERIES = {
        "projects": ProjectQueries.LIST,
    }

    def __init__(self, base_url: str, auth_client: AuthClient):
        self.base_url = f"{base_url}/api/graphql"
        self.auth_client = auth_client
        self._client = http_async_client

    async def get_resource(
        self, 
        resource_type: str,
        variables: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        query = self.RESOURCE_QUERIES.get(resource_type)
        if not query:
            raise ValueError(f"Unsupported resource type for GraphQL: {resource_type}")
            
        async for batch in self._execute_paginated_query(
            query=str(query),
            resource_field=resource_type,
            variables=variables
        ):
            yield batch

    async def _execute_paginated_query(
        self, 
        query: str, 
        resource_field: str,
        variables: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
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
                
            yield nodes
            
            page_info = resource_data.get("pageInfo", {})
            if not page_info.get("hasNextPage", False):
                break
                
            cursor = page_info.get("endCursor")

    async def _execute_query(
        self, query: str, variables: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        try:
            response = await self._client.post(
                self.base_url,
                headers=self.auth_client.get_headers(),
                json={
                    "query": query,
                    "variables": variables or {},
                },
            )
            response.raise_for_status()

            data = response.json()

            if "errors" in data:
                logger.error(f"GraphQL query failed: {data['errors']}")
                raise Exception(f"GraphQL query failed: {data['errors']}")

            return data.get("data", {})

        except Exception as e:
            logger.error(f"Failed to execute GraphQL query: {str(e)}")
            raise
