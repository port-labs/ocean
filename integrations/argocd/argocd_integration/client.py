from typing import Any, Optional
import httpx
from loguru import logger


class ArgocdClient:
    def __init__(
        self, token: str, server_url: str
    ):
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
        Makes an API request to the given URL

        Args:
            url (str): API endpoint URL
            method (str): HTTP method (default: 'GET')
            query_params (dict): Query parameters (default: None)
            json_data (dict): JSON data to send in request body (default: None)

        Returns:
            dict[str, Any]: A dictionary containing the JSON response from the resource.
        """
        try:
            response = await self.http_client.request(method=method, url=url, params=query_params, json=json_data)

            response.raise_for_status()
            return response.json()["items"]

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise


    async def get_argocd_resource(self, resource_type: str) -> list[dict[str, Any]]:
        """
        Retrieve ArgoCD resources of a specific type.

        Args:
            resource_type (str): The type of ArgoCD resource to retrieve.

        Returns:
            list[dict[str, Any]]: A list of dictionaries representing the ArgoCD resources
            of the specified type.
        """
        url = f"{self.api_url}/{resource_type}"
        return await self._send_api_request(url=url)

    async def get_argocd_deployments(self) -> list[dict[str, Any]]:
        """
        Retrieve a list of ArgoCD deployments.

        Returns:
            list[dict[str, Any]]: A list of dictionaries representing ArgoCD deployments.
        """
        applications = await self.get_argocd_resource(
            resource_type="applications"
        )
        all_deployments = []
        for application in applications:

            application_metadata = application.get("metadata", {})
            application_uid = application_metadata.get("uid")

            for resource in application.get("status", {}).get("resources", []):
                resource["application_uid"] = application_uid
                all_deployments.append(resource)

        return all_deployments