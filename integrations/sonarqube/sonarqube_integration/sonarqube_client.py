from typing import Any, Optional
import httpx
from loguru import logger


class Endpoints:
    PROJECTS = "components/search_projects"
    QUALITY_GATE_STATUS = "qualitygates/project_status"
    QUALITY_GATE_NAME = "qualitygates/get_by_project"
    WEBHOOKS = "webhooks"

class SonarQubeClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        organization_id: str,
        app_host: str,
        http_client: httpx.AsyncClient,
    ):
        """
        Initialize SonarQubeClient

        :param base_url: SonarQube base URL
        :param api_key: SonarQube API key
        :param organization_id: SonarQube organization ID
        :param app_host: Application host URL
        :param http_client: httpx.AsyncClient instance
        """
        self.base_url = base_url
        self.api_key = api_key
        self.organization_id = organization_id
        self.app_host = app_host
        self.http_client = http_client

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Sends an API request to SonarQube

        :param endpoint: API endpoint URL
        :param method: HTTP method (default: 'GET')
        :param query_params: Query parameters (default: None)
        :param json_data: JSON data to send in request body (default: None)
        :return: Response JSON data
        """
        try:
            response = await self.http_client.request(
                method=method,
                url=f"{self.base_url}/api/{endpoint}",
                params=query_params,
                json=json_data,
                headers=self.api_auth_header,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    async def get_projects(self) -> list[Any]:
        """A function to make API request to SonarQube and retrieve projects within an organization"""
        logger.info(f"Fetching all projects in organization: {self.organization_id}")
        response = await self.send_api_request(
            endpoint=Endpoints.PROJECTS,
            query_params={"organization": self.organization_id},
        )
        return response.get("components", [])

    async def get_quality_gate_status(
        self, project_key: str
    ) -> Optional[dict[str, Any]]:
        """
        Get quality gate status for a project

        :param project_key: Project key
        :return: Dictionary containing quality gate status or None if not available
        """
        logger.info(f"Fetching quality gate data in project: {project_key}")
        response = await self.send_api_request(
            endpoint=Endpoints.QUALITY_GATE_STATUS,
            query_params={"projectKey": project_key},
        )
        project_status = response.get("projectStatus", {})
        if project_status:
            return project_status
        else:
            logger.info(f"No quality gate data found for the project: {project_key}")
            return None

    async def get_quality_gate_name(self, project_key: str) -> Optional[str]:
        """
        Get quality gate name for a project

        :param project_key: Project key
        :return: Quality gate name or None if not available
        """
        logger.info(f"Fetching quality gate name in project: {project_key}")
        response = await self.send_api_request(
            endpoint=Endpoints.QUALITY_GATE_NAME,
            query_params={"project": project_key, "organization": self.organization_id},
        )
        quality_gate = response.get("qualityGate", {})
        if quality_gate:
            return quality_gate
        else:
            logger.info(f"No quality gate data found for the project: {project_key}")
            return None
            

    async def get_cloud_analysis_data_for_project(
        self, project: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Get quality gates analysis data for a project

        :param project: Project dictionary
        :return: Dictionaries containing cloud analysis data
        """
        logger.info(
            f'Fetching sonarqube quality analysis data for project: {project.get("key")}'
        )

        project_key = project.get("key", "")
        project_quality_status = await self.get_quality_gate_status(
            project_key=project_key
        )
        quality_gate_name = await self.get_quality_gate_name(project_key=project_key)
        project_quality_status.update(quality_gate_name)

        return project_quality_status


    async def get_or_create_webhook_url(self) -> None:
        """
        Get or create webhook URL for projects

        :return: None
        """
        logger.info(f"Subscribing to webhooks in organization: {self.organization_id}")
        webhook_endpoint = Endpoints.WEBHOOKS
        invoke_url = f"{self.app_host}/integration/webhook"
        projects = await self.get_projects()

        # Iterate over projects and add webhook
        webhooks_to_create = []
        for project in projects:
            project_key = project["key"]
            logger.info(f"Fetching existing webhooks in project: {project_key}")
            webhooks_response = await self.send_api_request(
                endpoint=f"{webhook_endpoint}/list",
                query_params={
                    "project": project_key,
                    "organization": self.organization_id,
                },
            )

            webhooks = webhooks_response.get("webhooks", [])
            logger.info(webhooks)

            if any(webhook["url"] == invoke_url for webhook in webhooks):
                logger.info(f"Webhook already exists in project: {project_key}")
                continue
            webhooks_to_create.append(
                {
                    "name": "Port Ocean Webhook",
                    "project": project_key,
                    "organization": self.organization_id,
                }
            )

        for webhook in webhooks_to_create:
            await self.send_api_request(
                endpoint=f"{webhook_endpoint}/create",
                method="POST",
                query_params={**webhook, "url": invoke_url},
            )
            logger.info(f"Webhook added to project: {webhook['project']}")
