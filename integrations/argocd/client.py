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
    MANAGED_RESOURCE = "managed-resource"


DEPRECATION_WARNING = "Please use the get_resources method with the application kind and map the response using the itemsToParse functionality. You can read more about parsing items here https://ocean.getport.io/framework/features/resource-mapping/#fields"


class ArgocdClient:
    def __init__(
        self,
        token: str,
        server_url: str,
        ignore_server_error: bool,
        allow_insecure: bool,
    ):
        self.token = token
        self.api_url = f"{server_url}/api/v1"
        self.ignore_server_error = ignore_server_error
        self.allow_insecure = allow_insecure
        self.api_auth_header = {"Authorization": f"Bearer {self.token}"}
        if self.allow_insecure:
            # This is not recommended for production use
            self.http_client = httpx.AsyncClient(verify=False)
        else:
            self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)

    async def _send_api_request(
        self,
        url: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        logger.info(f"Sending request to ArgoCD API: {method} {url}")
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
                f"Encountered an HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            if self.ignore_server_error:
                return {}
            raise e
        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} while sending a request to {method} {url} with query_params: {query_params}"
            )
            if self.ignore_server_error:
                return {}
            raise e

    async def get_resources(self, resource_kind: ObjectKind) -> list[dict[str, Any]]:
        url = f"{self.api_url}/{resource_kind}s"
        try:
            response_data = await self._send_api_request(url=url)
            return response_data["items"]
        except Exception as e:
            logger.error(f"Failed to fetch resources of kind {resource_kind}: {e}")
            if self.ignore_server_error:
                return []
            raise e

    async def get_application_by_name(self, name: str) -> dict[str, Any]:
        url = f"{self.api_url}/{ObjectKind.APPLICATION}s/{name}"
        application = await self._send_api_request(url=url)
        return application

    async def get_deployment_history(self) -> list[dict[str, Any]]:
        """The ArgoCD application route returns a history of all deployments. This function reuses the output of the application endpoint"""
        logger.warning(
            f"get_deployment_history is deprecated as of 0.1.34. {DEPRECATION_WARNING}"
        )
        applications = await self.get_resources(resource_kind=ObjectKind.APPLICATION)
        all_history = [
            {**history_item, "__applicationId": application["metadata"]["uid"]}
            for application in applications
            for history_item in application["status"].get("history", [])
        ]
        return all_history

    async def get_kubernetes_resource(self) -> list[dict[str, Any]]:
        """The ArgoCD application returns a list of managed kubernetes resources. This function reuses the output of the application endpoint"""
        logger.warning(
            f"get_kubernetes_resource is deprecated as of 0.1.34. {DEPRECATION_WARNING}"
        )
        applications = await self.get_resources(resource_kind=ObjectKind.APPLICATION)
        all_k8s_resources = [
            {**resource, "__applicationId": application["metadata"]["uid"]}
            for application in applications
            for resource in application["status"].get("resources", [])
        ]
        return all_k8s_resources

    async def get_managed_resources(
        self, application_name: str
    ) -> list[dict[str, Any]]:
        logger.info(f"Fetching managed resources for application: {application_name}")
        url = f"{self.api_url}/{ObjectKind.APPLICATION}s/{application_name}/managed-resources"
        managed_resources = (await self._send_api_request(url=url)).get("items", [])
        return managed_resources
