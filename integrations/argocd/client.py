from enum import StrEnum
from typing import Any, Optional, AsyncGenerator

import httpx
from loguru import logger
from port_ocean.utils import http_async_client


class ObjectKind(StrEnum):
    PROJECT = "project"
    APPLICATION = "application"


class ResourceKindsWithSpecialHandling(StrEnum):
    DEPLOYMENT_HISTORY = "deployment-history"
    KUBERNETES_RESOURCE = "kubernetes-resource"
    MANAGED_RESOURCE = "managed-resource"
    CLUSTER = "cluster"


DEPRECATION_WARNING = "Please use the get_resources method with the application kind and map the response using the itemsToParse functionality. You can read more about parsing items here https://ocean.getport.io/framework/features/resource-mapping/#fields"

PAGE_SIZE = 100


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
            logger.warning(
                "Insecure mode is enabled. This will disable SSL verification for the ArgoCD API client, which is not recommended for production use."
            )
            self.http_client = httpx.AsyncClient(verify=False)
        else:
            self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)

    @staticmethod
    def _is_cluster_unreachable_exception(
        exception: Exception, kind: ObjectKind | ResourceKindsWithSpecialHandling
    ) -> bool:
        if isinstance(exception, (httpx.ConnectError, httpx.TimeoutException)):
            logger.warning(
                f"Connection to cluster timed out. Skipping ingestion for kind {kind}: {exception}"
            )
            return True

        if isinstance(exception, httpx.HTTPError):
            logger.warning(
                f"Cluster is unreachable. Skipping ingestion for kind {kind}: {exception}"
            )
            return "connection attempts failed" in str(exception).lower()

        return False

    async def _send_api_request(
        self,
        url: str,
        kind: ObjectKind | ResourceKindsWithSpecialHandling,
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
            if self._is_cluster_unreachable_exception(e, kind):
                return {}
            raise e

    async def get_resources(self, resource_kind: ObjectKind) -> list[dict[str, Any]]:
        url = f"{self.api_url}/{resource_kind}s"
        try:
            response_data = await self._send_api_request(url=url, kind=resource_kind)
            return response_data.get("items", [])
        except Exception as e:
            if self.ignore_server_error:
                return []
            logger.error(f"Failed to fetch resources of kind {resource_kind}: {e}")
            raise e

    async def get_clusters(self) -> list[dict[str, Any]]:
        url = f"{self.api_url}/{ResourceKindsWithSpecialHandling.CLUSTER}s"
        try:
            response_data = await self._send_api_request(
                url=url, kind=ResourceKindsWithSpecialHandling.CLUSTER
            )
            return response_data.get("items", [])
        except Exception as e:
            if self.ignore_server_error:
                return []
            raise e

    async def get_application_by_name(self, name: str) -> dict[str, Any]:
        url = f"{self.api_url}/{ObjectKind.APPLICATION}s/{name}"
        application = await self._send_api_request(url=url, kind=ObjectKind.APPLICATION)
        return application

    async def get_deployment_history(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """The ArgoCD application route returns a history of all deployments. This function reuses the output of the application endpoint"""
        logger.warning(
            f"get_deployment_history is deprecated as of 0.1.34. {DEPRECATION_WARNING}"
        )
        applications = await self.get_resources(resource_kind=ObjectKind.APPLICATION)
        if not applications:
            logger.error(
                "No applications were found. Skipping deployment history ingestion"
            )
        else:
            batch: list[dict[str, Any]] = []
            for application in applications:
                history = application.get("status", {}).get("history", [])
                if history:
                    for item in history:
                        batch.append(item)
                        if len(batch) >= PAGE_SIZE:
                            yield batch
                            batch = []

            if batch:
                yield batch

    async def get_kubernetes_resource(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """The ArgoCD application returns a list of managed kubernetes resources. This function reuses the output of the application endpoint"""
        logger.warning(
            f"get_kubernetes_resource is deprecated as of 0.1.34. {DEPRECATION_WARNING}"
        )
        applications = await self.get_resources(resource_kind=ObjectKind.APPLICATION)
        if not applications:
            logger.error(
                "No applications were found. Skipping managed resources ingestion"
            )
            return

        batch: list[dict[str, Any]] = []
        for app in applications:
            if not app["metadata"]["uid"]:
                logger.warning(
                    f"Skipping application without UID: {app.get('metadata', {}).get('name', 'unknown')}"
                )
                continue

            resources = [
                {
                    **resource,
                    "__application": app,
                }
                for resource in app.get("status", {}).get("resources", [])
                if resource
            ]

            for resource in resources:
                batch.append(resource)
                if len(batch) >= PAGE_SIZE:
                    yield batch
                    batch = []

        if batch:
            yield batch

    async def get_managed_resources(
        self, application: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        errors = []
        try:
            application_name = application["metadata"]["name"]
            logger.info(
                f"Fetching managed resources for application: {application_name}"
            )
            kind = ObjectKind.APPLICATION
            url = f"{self.api_url}/{kind}s/{application_name}/managed-resources"
            managed_resources = (await self._send_api_request(url=url, kind=kind)).get(
                "items", []
            )

            batch: list[dict[str, Any]] = []
            for managed_resource in managed_resources:
                if managed_resource:
                    resource = {
                        **managed_resource,
                        "__application": application,
                    }
                    batch.append(resource)

                    if len(batch) >= PAGE_SIZE:
                        yield batch
                        batch = []

            if batch:
                yield batch

        except Exception as e:
            logger.error(
                f"Failed to fetch managed resources for application {application['metadata']['name']}: {e}"
            )
            errors.append(e)

        if errors and not self.ignore_server_error:
            raise ExceptionGroup(
                "Errors occurred during managed resource ingestion", errors
            )
