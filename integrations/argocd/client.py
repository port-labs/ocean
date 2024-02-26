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
    KUBERNETES_RESOURCE = "kubernetes-resource"


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
        url = f"{self.api_url}/{resource_kind}s"
        response_data = (await self._send_api_request(url=url))["items"]
        return response_data

    async def get_application_by_name(self, name: str) -> dict[str, Any]:
        url = f"{self.api_url}/{ObjectKind.APPLICATION}s/{name}"
        application = await self._send_api_request(url=url)
        return application

    async def get_deployment_history(self) -> list[dict[str, Any]]:
        """The ArgoCD application route returns a history of all deployments. This function reuses the output of the application endpoint"""
        logger.info("fetching Argocd deployment history from applications endpoint")
        applications = await self.get_resources(resource_kind=ObjectKind.APPLICATION)
        all_history = [
            {**history_item, "__applicationId": application["metadata"]["uid"]}
            for application in applications
            for history_item in application["status"].get("history", [])
        ]
        return all_history

    async def get_kubernetes_resource(self) -> list[dict[str, Any]]:
        """The ArgoCD application returns a list of managed kubernetes resources. This function reuses the output of the application endpoint"""
        logger.info("fetching Argocd managed k8s resources from applications endpoint")
        applications = await self.get_resources(resource_kind=ObjectKind.APPLICATION)
        all_k8s_resources = [
            {**resource, "__applicationId": application["metadata"]["uid"]}
            for application in applications
            for resource in application["status"].get("resources", [])
        ]
        return all_k8s_resources
