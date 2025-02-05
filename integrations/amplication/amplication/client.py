from loguru import logger

from port_ocean.utils import http_async_client
from typing import Any, Optional
from .queries import TEMPLATE_QUERY, RESOURCE_QUERY, ALERTS_QUERY


class AmplicationClient:
    def __init__(self, api_url: str, api_token: str):
        self.api_url = api_url
        self.api_token = api_token
        self.client = http_async_client

    @property
    async def auth_headers(self) -> dict[str, Any]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    async def _execute_graphql_query(
        self, query: str, variables: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Execute a GraphQL query and handle common error cases"""
        payload = {
            "query": query,
            "variables": variables or {},
        }

        response = await self.client.post(
            self.api_url,
            json=payload,
            headers=await self.auth_headers,
        )
        response.raise_for_status()

        data = response.json()
        if not isinstance(data, dict):
            logger.error(f"Unexpected response structure from Amplication API: {data}")
            return {}
        return data

    async def get_templates(self) -> list[dict[str, Any]]:
        logger.info("Getting templates from Amplication")
        variables = {
            "take": 100,
            "skip": 0,
            "where": {"resourceType": {"in": ["ServiceTemplate"]}},
        }

        data = await self._execute_graphql_query(TEMPLATE_QUERY, variables)
        if (
            "data" not in data
            or "catalog" not in data["data"]
            or "data" not in data["data"]["catalog"]
        ):
            logger.error(f"Unexpected response structure from Amplication API: {data}")
            return []
        return data["data"]["catalog"]["data"]

    async def get_resources(self) -> list[dict[str, Any]]:
        logger.info("Getting resources from Amplication")
        variables = {
            "take": 100,
            "skip": 0,
            "where": {"resourceType": {"in": ["Service", "Component"]}},
        }

        data = await self._execute_graphql_query(RESOURCE_QUERY, variables)
        if (
            "data" not in data
            or "catalog" not in data["data"]
            or "data" not in data["data"]["catalog"]
        ):
            logger.error(f"Unexpected response structure from Amplication API: {data}")
            return []
        return data["data"]["catalog"]["data"]

    async def get_alerts(self) -> list[dict[str, Any]]:
        logger.info("Getting alerts from Amplication")
        variables = {"orderBy": {"createdAt": "Desc"}, "take": 100, "skip": 0}

        data = await self._execute_graphql_query(ALERTS_QUERY, variables)
        if "data" not in data or "outdatedVersionAlerts" not in data["data"]:
            logger.error(f"Unexpected response structure from Amplication API: {data}")
            return []
        return data["data"]["outdatedVersionAlerts"]
