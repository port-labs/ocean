from typing import Any, Optional
import httpx
from loguru import logger


class SnykClient:
    def __init__(
        self, token: str, api_url: str, app_host: str, org_id: str, webhook_secret: str
    ):
        self.token = token
        self.api_url = f"{api_url}/v1"
        self.app_host = app_host
        self.org_id = org_id
        self.rest_api_url = f"{api_url}/rest"
        self.webhook_secret = webhook_secret
        self.http_client = httpx.AsyncClient(headers=self.api_auth_header)

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {"Authorization": f"token {self.token}"}

    async def _send_api_request(
        self,
        url: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Fetches a single resource from the given Snyk URL using an HTTP GET/POST request.

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

    async def _get_paginated_resources(
        self, base_url: str, url_path: str, method: str = "GET", data_key: str = "data"
    ) -> list[Any]:
        """
        Retrieves a list of paginated resources from Snyk

        Args:
            base_url (str): The base URL of the API.
            url_path (str): The path for the current endpoint.
            data_key (str): The key for the data in the API response.

        Returns:
            list[Any]: A list of paginated resources.
        """
        all_data = []

        while (
            url_path
        ):  # loop as long as there is a "next" property in the paginated response from Snyk
            try:
                full_url = f"{base_url}{url_path}"
                response = await self.http_client.request(method=method, url=full_url)
                response.raise_for_status()
                data = response.json()

                all_data.extend(data[data_key])

                # Check if there is a "next" URL in the links object
                url_path = data.get("links", {}).get("next")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
        return all_data

    async def get_vulnerabilities(
        self, project: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Fetches all vulnerabilities associated with the provided project.

        Args:
            project (dict[str, Any]): A dictionary representing the project for which vulnerabilities need to be fetched. The project dictionary should contain necessary information like project ID.

        Returns:
            list[dict[str, Any]]: A list of dictionaries, each representing a vulnerability associated with the provided project. Each vulnerability dictionary includes details about the vulnerability.
        """
        url = f"/org/{self.org_id}/project/{project.get('id')}/aggregated-issues"
        try:
            issues_data = await self._get_paginated_resources(
                base_url=self.api_url, url_path=url, method="POST", data_key="issues"
            )
            return issues_data
        except Exception as e:
            logger.error(
                f"Error fetching vulnerabilities for project: {project.get('id')} error: {e}"
            )
            raise

    async def get_targets(self) -> list[dict[str, Any]]:
        """
        Fetches a list of target entities from Snyk.

        Returns:
            list[dict[str, Any]]: A list of dictionaries, where each dictionary represents a target entity.
        """
        url = f"/orgs/{self.org_id}/targets?version=2022-12-21~beta"
        return await self._get_paginated_resources(
            base_url=self.rest_api_url, url_path=url
        )

    async def get_projects(self) -> list[dict[str, Any]]:
        """
        Fetches a list of projects from Snyk.

        Returns:
            list[dict[str, Any]]: A list of dictionaries, where each dictionary represents a target entity.
        """
        url = f"/orgs/{self.org_id}/projects?version=2023-06-19"
        return await self._get_paginated_resources(
            base_url=self.rest_api_url, url_path=url
        )

    async def create_webhooks_if_not_exists(self) -> None:
        """
        Creates Snyk webhooks if they do not already exist.

        This function checks for the presence of webhooks and creates them if they are not already set up.
        It ensures that the necessary webhooks for certain events are in place to enable event notifications

        Returns:
            None: This function does not return a value; it either creates the required webhooks or leaves
                them unchanged based on their existence.
        """
        snyk_webhook_url = f"{self.api_url}/org/{self.org_id}/webhooks"
        all_subscriptions = await self._send_api_request(
            url=snyk_webhook_url, method="GET"
        )

        app_host_webhook_url = f"{self.app_host}/integration/webhook"

        for webhook in all_subscriptions.get("results", []):
            if webhook["url"] == app_host_webhook_url:
                return

        body = {"url": app_host_webhook_url, "secret": self.webhook_secret}

        await self._send_api_request(
            url=snyk_webhook_url, method="POST", json_data=body
        )
