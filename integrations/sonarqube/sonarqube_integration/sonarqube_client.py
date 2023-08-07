from typing import Any
import httpx
from loguru import logger

class Endpoints:
    PROJECTS = "components/search"
    BRANCHES = "project_branches/list"
    QUALITY_GATE_STATUS = "qualitygates/project_status"
    QUALITY_GATE_NAME = "qualitygates/get_by_project"
    WEBHOOKS = "webhooks"

class SonarQubeClient:
    def __init__(self, base_url, api_key, organization_id, app_host):
        self.base_url = base_url
        self.api_key = api_key
        self.organization_id = organization_id
        self.app_host = app_host
    
    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}

    async def send_api_request(self, client, endpoint, method='GET', query_params=None, json_data=None):
        try:
            async with client.request(method=method, url=f"{self.base_url}/api/{endpoint}", params=query_params, json=json_data, headers=self.api_auth_header) as response:
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            raise
    
    async def get_projects(self, client):
        """A function to make API request to SonarQube and retrieve projects within an organization"""
        endpoint_url = Endpoints.PROJECTS
        response = await self.send_api_request(client=client, endpoint=endpoint_url, query_params={"organization": self.organization_id})
        return response.get("components", [])

    async def get_branches(self, client, project_key):
        """A function to retrieve branch information from a project"""
        endpoint_url = Endpoints.BRANCHES
        response = await self.send_api_request(client=client, endpoint=endpoint_url, query_params={"project": project_key})
        return response.get("branches", [])

    async def get_quality_gate_status(self, client, project_key):
        """A function to get the quality gate status of a project"""
        endpoint_url = Endpoints.QUALITY_GATE_STATUS
        response = await self.send_api_request(client=client, endpoint=endpoint_url, query_params={"projectKey": project_key})
        return response.get("projectStatus", {})

    async def get_quality_gate_name(self, client, project_key):
        """A function to get the quality gate of a project"""
        endpoint_url = Endpoints.QUALITY_GATE_NAME
        response = await self.send_api_request(client=client, endpoint=endpoint_url, query_params={"project": project_key, "organization": self.organization_id})
        return response.get("qualityGate", {}).get("name", "")
    
    async def get_sonarqube_cloud_analysis(self):
        """Get's sonarqube cloud analysis"""
        pass

    async def get_or_create_webhook_url(self):
        """Create webhook"""
        webhook_endpoint = Endpoints.WEBHOOKS
        async with httpx.AsyncClient() as client:
            projects = self.get_projects(client=client)

            # Iterate over projects and add webhook
            webhooks_to_create = []
            for project in projects:
                project_key = project["key"]
                logger.info(f'Fetching existing webhooks in the project: {project_key}')
                webhooks = self.send_api_request(client=client, endpoint=f'{webhook_endpoint}/list', query_params={
                    "project": project_key,
                    "organization": self.organization_id
                })['webhooks']

                if [webhook for webhook in webhooks if webhook['url'] == self.app_host]:
                    logger.info(f"Webhook already exists in project: {project_key}")
                    continue
                webhooks_to_create.append({
                    "name": "Port Ocean Webhook",
                    "project": project_key,
                    "organization": self.organization_id
                })
            
            for webhook in webhooks_to_create:
                self.send_api_request(client=client, endpoint=f'{webhook_endpoint}/create', method='POST', json_data={
                    **webhook,
                    "url": self.app_host
                })
                logger.info(f"Webhook added to project: {webhook['project']}")