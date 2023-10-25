from typing import Any, Optional, AsyncGenerator
import httpx
from loguru import logger
from argocd_integration.utils import ObjectKind
from port_ocean.context.event import event


class ArgocdClient:
    def __init__(self, token: str, server_url: str):
        self.token = token
        self.api_url = f"{server_url}/api/v1"
        self.http_client = httpx.AsyncClient(headers=self.api_auth_header, verify=False)

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {"Authorization": f"Bearer {self.token}"}

    async def _send_api_request(
        self,
        url: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            response = await self.http_client.request(
                method=method, url=url, params=query_params, json=json_data,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    async def get_resources(self, resource_kind: ObjectKind) -> list[dict[str, Any]]:

        url = f"{self.api_url}/{resource_kind.value}s"
        cache_key = resource_kind

        if cache := event.attributes.get(cache_key):
            return cache
        response_data = (await self._send_api_request(url=url))["items"]
        event.attributes[cache_key] = response_data
        return response_data
    
    async def get_all_applications(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve all ArgoCD applications across all projects. Due to the unavailability of server-side pagination in the ArgoCD REST API, 
        we can temporary resolve it by filtering with projects. This will solve the issue of having a very huge data in one network call

        Returns:
            List[dict[str, Any]]: A list of dictionaries representing ArgoCD applications.
        """
        projects = await self.get_resources(ObjectKind.PROJECT)
        url = f"{self.api_url}/{ObjectKind.APPLICATION}s"

        cache_key = ObjectKind.APPLICATION
        if cache := event.attributes.get(cache_key):
            yield cache
            return
        
        for project in projects:
            project_name = project["metadata"]["name"]
            applications_data = await self._send_api_request(
                url=url, query_params={"projects": project_name}
            )
            applications = applications_data["items"]
            if applications:
                yield applications
                event.attributes.setdefault(cache_key, []).extend(applications)


    async def get_application_by_name(self, name: str) -> dict[str, Any]:

        url = f"{self.api_url}/{ObjectKind.APPLICATION}s/{name}"

        cache_key = f"{ObjectKind.APPLICATION}-{name}"
        if cache := event.attributes.get(cache_key):
            return cache
        
        application = await self._send_api_request(
            url=url
        )
        event.attributes[cache_key] = application
        return application

