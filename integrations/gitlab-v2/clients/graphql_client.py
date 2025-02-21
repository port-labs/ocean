from typing import AsyncIterator, Optional, Any
from loguru import logger
from .auth_client import AuthClient
from .queries import ProjectQueries
from port_ocean.utils import http_async_client


class GraphQLClient:
    def __init__(self, base_url: str, auth_client: AuthClient):
        self.base_url = f"{base_url}/api/graphql"
        self.auth_client = auth_client
        self._client = http_async_client

    async def execute_query(
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
