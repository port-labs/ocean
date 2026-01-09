from enum import StrEnum
from typing import Any, Optional, AsyncGenerator

import httpx
from loguru import logger

from port_ocean.helpers.async_client import OceanAsyncClient, StreamingClientWrapper
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


class ClusterState(StrEnum):
    AVAILABLE = "Successful"


class ArgocdClient:
    def __init__(
        self,
        token: str,
        server_url: str,
        ignore_server_error: bool,
        allow_insecure: bool,
        use_streaming: bool = False,
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
            self.http_client = OceanAsyncClient(verify=False)
        else:
            # Type ignore because http_async_client is typed as AsyncClient but returns OceanAsyncClient
            self.http_client = http_async_client  # type: ignore
        self.http_client.headers.update(self.api_auth_header)
        self.streaming_client = StreamingClientWrapper(self.http_client)
        self.use_streaming = use_streaming

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

    async def get_clusters(
        self, skip_unavailable_clusters: bool = False
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f"{self.api_url}/{ResourceKindsWithSpecialHandling.CLUSTER}s"
        try:
            if self.use_streaming:
                async for clusters in self.streaming_client.stream_json(
                    url=url, target_items_path="items"
                ):
                    if skip_unavailable_clusters:
                        yield [
                            cluster
                            for cluster in clusters
                            if cluster.get("connectionState", {}).get("status")
                            == ClusterState.AVAILABLE.value
                        ]
                    else:
                        yield clusters
            else:
                response_data = await self._send_api_request(url=url)
                clusters = response_data.get("items", [])

                if skip_unavailable_clusters:
                    clusters = [
                        cluster
                        for cluster in clusters
                        if cluster.get("connectionState", {}).get("status")
                        == ClusterState.AVAILABLE.value
                    ]

                # Yield in batches of PAGE_SIZE
                batch = []
                for cluster in clusters:
                    batch.append(cluster)
                    if len(batch) >= PAGE_SIZE:
                        yield batch
                        batch = []

                if batch:
                    yield batch
        except Exception as e:
            logger.error(f"Failed to fetch clusters: {e}")
            if not self.ignore_server_error:
                raise

    async def get_available_clusters(self) -> list[dict[str, Any]]:
        available_clusters: list[dict[str, Any]] = []
        async for clusters in self.get_clusters(skip_unavailable_clusters=True):
            available_clusters.extend(clusters)
        return available_clusters

    async def get_resources_for_available_clusters(
        self, resource_kind: ObjectKind
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        available_clusters = await self.get_available_clusters()
        cluster_names = [cluster["name"] for cluster in available_clusters]
        url = f"{self.api_url}/{resource_kind}s"

        all_resources = []
        for cluster_name in cluster_names:
            try:
                if self.use_streaming:
                    async for resources in self.streaming_client.stream_json(
                        url=url,
                        target_items_path="items",
                        params={"cluster": cluster_name},
                    ):
                        all_resources.extend(resources)
                else:
                    response_data = await self._send_api_request(
                        url=url, query_params={"cluster": cluster_name}
                    )
                    all_resources.extend(response_data.get("items", []))
            except Exception as e:
                logger.error(
                    f"Failed to fetch resources of kind {resource_kind} for cluster {cluster_name}: {e}"
                )
                if not self.ignore_server_error:
                    raise

        # Yield in batches of PAGE_SIZE
        batch = []
        for resource in all_resources:
            batch.append(resource)
            if len(batch) >= PAGE_SIZE:
                yield batch
                batch = []

        if batch:
            yield batch

    async def get_application_by_name(self, name: str, namespace: Optional[str] = None) -> dict[str, Any]:
        url = f"{self.api_url}/{ObjectKind.APPLICATION}s/{name}"
        query_params = {}
        if namespace:
            query_params["appNamespace"] = namespace
        application = await self._send_api_request(url=url, query_params=query_params)
        return application

    async def get_deployment_history(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """The ArgoCD application route returns a history of all deployments. This function reuses the output of the application endpoint"""
        logger.warning(
            f"get_deployment_history is deprecated as of 0.1.34. {DEPRECATION_WARNING}"
        )
        batch: list[dict[str, Any]] = []
        has_applications = False
        async for applications in self.get_resources_for_available_clusters(
            resource_kind=ObjectKind.APPLICATION
        ):
            has_applications = True
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

        if not has_applications:
            logger.error(
                "No applications were found. Skipping deployment history ingestion"
            )

    async def get_kubernetes_resource(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """The ArgoCD application returns a list of managed kubernetes resources. This function reuses the output of the application endpoint"""
        logger.warning(
            f"get_kubernetes_resource is deprecated as of 0.1.34. {DEPRECATION_WARNING}"
        )
        batch: list[dict[str, Any]] = []
        has_applications = False
        async for applications in self.get_resources_for_available_clusters(
            resource_kind=ObjectKind.APPLICATION
        ):
            has_applications = True
            for app in applications:
                if not app.get("metadata", {}).get("uid"):
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

        if not has_applications:
            logger.error(
                "No applications were found. Skipping managed resources ingestion"
            )

    async def get_managed_resources(
        self, application: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        try:
            application_name = application["metadata"]["name"]
            logger.info(
                f"Fetching managed resources for application: {application_name}"
            )
            url = f"{self.api_url}/{ObjectKind.APPLICATION}s/{application_name}/managed-resources"

            if self.use_streaming:
                async for managed_resources in self.streaming_client.stream_json(
                    url=url, target_items_path="items"
                ):
                    yield [
                        {**managed_resource, "__application": application}
                        for managed_resource in managed_resources
                        if managed_resource
                    ]
            else:
                response_data = await self._send_api_request(url=url)
                managed_resources = response_data.get("items", [])

                # Yield in batches of PAGE_SIZE
                batch = []
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
            if not self.ignore_server_error:
                raise
