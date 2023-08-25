from typing import Any, Optional, AsyncGenerator
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
        self.snyk_api_version = "2023-08-21"
        self.user_details_cache: dict[
            str, Any
        ] = (
            {}
        )  ## used as a temporary in-memory object to avoid making API call for the same user

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
        self,
        base_url: str,
        url_path: str,
        method: str = "GET",
        data_key: str = "data",
        query_params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[Any], None]:
        """
        Retrieves paginated resources from Snyk as an asynchronous generator.

        Args:
            base_url (str): The base URL of the API.
            url_path (str): The path for the current endpoint.
            data_key (str): The key for the data in the API response.
            query_params (dict): Query parameters (default: None)

        Yields:
            list[Any]: A list of paginated resources.
        """
        while url_path:
            try:
                full_url = f"{base_url}{url_path}"
                response = await self.http_client.request(
                    method=method, url=full_url, params=query_params
                )
                response.raise_for_status()
                data = response.json()

                yield data[data_key]

                # Check if there is a "next" URL in the links object
                url_path = data.get("links", {}).get("next")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise

    async def get_vulnerabilities(
        self, project: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetches all vulnerabilities associated with the provided project as an asynchronous generator.

        Args:
            project (dict[str, Any]): A dictionary representing the project for which vulnerabilities need to be fetched. The project dictionary should contain necessary information like project ID.

        Yields:
            dict[str, Any]: A dictionary representing a vulnerability associated with the provided project.
        """
        url = f"/org/{self.org_id}/project/{project.get('id')}/aggregated-issues"
        try:
            async for issues_data in self._get_paginated_resources(
                base_url=self.api_url, url_path=url, method="POST", data_key="issues"
            ):
                yield issues_data
        except Exception as e:
            logger.error(
                f"Error fetching vulnerabilities for project: {project.get('id')} error: {e}"
            )
            raise

    async def get_paginated_projects(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetches projects from Snyk as an asynchronous generator.

        Yields:
            dict[str, Any]: A dictionary representing a project.
        """
        url = f"/orgs/{self.org_id}/projects"
        query_params = {
            "version": self.snyk_api_version,
            "meta.latest_issue_counts": "true",
            "expand": "target",
        }
        async for project_data in self._get_paginated_resources(
            base_url=self.rest_api_url, url_path=url, query_params=query_params
        ):
            yield project_data

    async def get_single_project(self, project: dict[str, Any]) -> dict[str, Any]:
        """
        Fetches a single project from Snyk.

        Params:
            project (dict[str, Any]): A dictionary representing the project. The project dictionary should contain necessary information like project ID.

        Returns:
            dict[str, Any]: A dictionary representing the project entity.
        """
        url = f"{self.rest_api_url}/orgs/{self.org_id}/projects/{project.get('id')}"
        query_params = {
            "version": self.snyk_api_version,
            "meta.latest_issue_counts": "true",
            "expand": "target",
        }
        response = await self._send_api_request(
            url=url, method="GET", query_params=query_params
        )
        return response.get("data", {})

    async def get_cached_user_details(self, user_id: str) -> dict[str, Any]:
        """
        Fetches user details from the cache if available, or makes an API call and caches the response.
        """
        if (
            not user_id
        ):  ## Some projects may not have been assigned to any owner yet. In this instance, we can return an empty dict
            return {}
        cached_details = self.user_details_cache.get(user_id)
        if cached_details:
            return cached_details

        user_details = await self._send_api_request(
            url=f"{self.api_url}/user/{user_id}"
        )
        self.user_details_cache[user_id] = user_details
        return user_details

    async def update_project_users(
        self, projects: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Updates the projects by fetching the owner and importer from Snyk

        Params:
            projects (list): A list of projects to retrieves their onwers and importers details

        Returns:
            list[dict[str, Any]]: A list of dictionaries, where each dictionary represents a project entity.
        """
        updated_projects = []
        for project in projects:
            owner_id = (
                project.get("relationships", {})
                .get("owner", {})
                .get("data", {})
                .get("id")
            )
            importer_id = (
                project.get("relationships", {})
                .get("importer", {})
                .get("data", {})
                .get("id")
            )

            owner_details = await self.get_cached_user_details(owner_id)
            importer_details = await self.get_cached_user_details(importer_id)

            project["_owner"] = owner_details
            project["_importer"] = importer_details

            updated_projects.append(project)
        return updated_projects

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
