from enum import StrEnum
from typing import Any, Optional

import httpx
from loguru import logger

from port_ocean.utils import http_async_client


class ObjectKind(StrEnum):
    PROJECT = "project"
    APPLICATION = "application"
    CLUSTER = "cluster"


class ResourceKindsWithSpecialHandling(StrEnum):
    DEPLOYMENT_HISTORY = "deployment-history"
    MANAGED_RESOURCE = "managed-resource"


class ArgocdClient:
    def __init__(self, token: str, server_url: str):
        self.token = token
        self.api_url = f"{server_url}/api/v1"
        self.api_auth_header = {"Authorization": f"Bearer {self.token}"}
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)

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
        logger.info(f"Fetching ArgoCD resource: {resource_kind}")
        url = f"{self.api_url}/{resource_kind}s"
        response_data = (await self._send_api_request(url=url))["items"]
        return response_data

    async def get_application_by_name(self, name: str) -> dict[str, Any]:
        url = f"{self.api_url}/{ObjectKind.APPLICATION}s/{name}"
        application = await self._send_api_request(url=url)
        return application

    async def get_deployment_history(self) -> list[dict[str, Any]]:
        """The ArgoCD application route returns a history of all deployments. This function reuses the output of the application endpoint"""
        applications = await self.get_resources(resource_kind=ObjectKind.APPLICATION)
        all_history = [
            {**history_item, "__applicationId": application["metadata"]["uid"]}
            for application in applications
            for history_item in application["status"].get("history", [])
        ]
        return all_history

    async def get_managed_resources(
        self, application_name: str
    ) -> list[dict[str, Any]]:
        logger.info(f"Fetching managed resources for application: {application_name}")
        url = f"{self.api_url}/{ObjectKind.APPLICATION}s/{application_name}/managed-resources"
        managed_resources = (await self._send_api_request(url=url))["items"]
        return managed_resources
