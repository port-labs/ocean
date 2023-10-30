from typing import Any, Optional
import httpx
from loguru import logger
from enum import StrEnum


class ObjectKind(StrEnum):
    PROJECT = "project"
    APPLICATION = "application"
    CLUSTER = "cluster"


class ArgocdClient:
    def __init__(self, token: str, server_url: str):
        self.token = token
        self.api_url = f"{server_url}/api/v1"
        self.api_auth_header = {"Authorization": f"Bearer {self.token}"}
        self.http_client = httpx.AsyncClient(headers=self.api_auth_header, verify=False)

    async def _send_api_request(
        self,
        url: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                params=query_params,
                json=json_data,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while fetching ArgoCD data {e}")
            raise

    async def get_resources(self, resource_kind: ObjectKind) -> list[dict[str, Any]]:
        url = f"{self.api_url}/{resource_kind}s"
        response_data = (await self._send_api_request(url=url))["items"]
        return response_data

    async def get_application_by_name(self, name: str) -> dict[str, Any]:
        url = f"{self.api_url}/{ObjectKind.APPLICATION}s/{name}"
        application = await self._send_api_request(url=url)
        return application
