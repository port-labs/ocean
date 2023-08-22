from typing import Any, Optional
import httpx
from loguru import logger
from argocd_integration.utils import ObjectKind


class ArgocdClient:
    def __init__(self, token: str, server_url: str):
        self.token = token
        self.api_url = f"{server_url}/api/v1"
        self.http_client = httpx.AsyncClient(headers=self.api_auth_header)

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
        """
        Makes an API request to the given URL. The Argo CD REST API documentation can be found here https://cd.apps.argoproj.io/swagger-ui

        Args:
            url (str): API endpoint URL
            method (str): HTTP method (default: 'GET')
            query_params (dict): Query parameters (default: None)
            json_data (dict): JSON data to send in request body (default: None)

        Returns:
            dict[str, Any]: A dictionary containing the JSON response from the resource.
        """
        try:
            response = await self.http_client.request(
                method=method, url=url, params=query_params, json=json_data
            )

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    async def get_argocd_projects(self) -> list[dict[str, Any]]:
        """
        Retrieves all ArgoCD projects

        Returns:
            list[dict[str, Any]]: A list of dictionaries representing the ArgoCD resources
            of the specified type.
        """
        url = f"{self.api_url}/{ObjectKind.PROJECT}"

        response = await self._send_api_request(url=url)
        return response.get("items", [])

    async def get_argocd_applications(self) -> list[dict[str, Any]]:
        """
        Retrieve all ArgoCD applications across all projects. Due to the unavailability of server-side pagination in the ArgoCD REST API, we can temporary resolve it by filtering with projects. This will solve the issue of having a very huge data in the network call

        Returns:
            List[dict[str, Any]]: A list of dictionaries representing ArgoCD applications.
        """
        projects = await self.get_argocd_projects()
        all_applications = []
        url = f"{self.api_url}/{ObjectKind.APPLICATION}"

        for project in projects:
            project_name = project.get("metadata", {}).get("name")
            applications = await self._send_api_request(
                url=url, query_params={"projects": project_name}
            )
            all_applications.extend(applications.get("items", [])) if applications.get(
                "items"
            ) else None

        return all_applications

    async def get_argocd_deployments(self) -> list[dict[str, Any]]:
        """
        Retrieve a list of ArgoCD deployments. We define deployment as all the resources contained in an application

        Returns:
            list[dict[str, Any]]: A list of dictionaries representing ArgoCD deployments.
        """
        applications = await self.get_argocd_applications()
        all_deployments = []
        for application in applications:
            application_metadata = application.get("metadata", {})
            application_uid = application_metadata.get("uid")

            for resource in application.get("status", {}).get("resources", []):
                resource["application_uid"] = application_uid
                all_deployments.append(resource)

        return all_deployments
