from loguru import logger

from port_ocean.utils import http_async_client
from typing import Any, Optional
from .queries import TEMPLATE_QUERY, RESOURCE_QUERY, ALERTS_QUERY

import httpx


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
        payload = {
            "query": query,
            "variables": variables or {},
        }

        try:
            response = await self.client.post(
                self.api_url,
                json=payload,
                headers=await self.auth_headers,
            )
            response.raise_for_status()
            response_json = response.json()

            return response_json["data"]
        except httpx.HTTPError as e:
            logger.error(f"Error while making GraphQL query: {str(e)}")
            raise

    async def get_templates(self) -> list[dict[str, Any]]:
        logger.info("Getting templates from Amplication")
        variables = {
            "take": 100,
            "skip": 0,
            "where": {"resourceType": {"in": ["ServiceTemplate"]}},
        }

        try:
            data = await self._execute_graphql_query(TEMPLATE_QUERY, variables)
            return data["catalog"]["data"]
        except Exception as e:
            logger.error(f"Error while getting templates from Amplication: {str(e)}")
            raise

    async def get_resources(self) -> list[dict[str, Any]]:
        logger.info("Getting resources from Amplication")
        variables = {
            "take": 100,
            "skip": 0,
            "where": {"resourceType": {"in": ["Service", "Component"]}},
        }

        try:
            data = await self._execute_graphql_query(RESOURCE_QUERY, variables)
            return data["catalog"]["data"]
        except Exception as e:
            logger.error(f"Error while getting resources from Amplication: {str(e)}")
            raise

    async def get_alerts(self) -> list[dict[str, Any]]:
        logger.info("Getting alerts from Amplication")
        variables = {"orderBy": {"createdAt": "Desc"}, "take": 100, "skip": 0}

        try:
            data = await self._execute_graphql_query(ALERTS_QUERY, variables)
            return data["outdatedVersionAlerts"]
        except Exception as e:
            logger.error(f"Error while getting alerts from Amplication: {str(e)}")
            raise
