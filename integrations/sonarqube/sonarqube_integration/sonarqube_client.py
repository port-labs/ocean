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
    
    async def get_sonarqube_cloud_analysis(self, client):
        """Get's sonarqube cloud analysis"""

        all_quality_gates_data = []
        projects = await self.get_projects(client=client)
        ## Iterate through the components array and create port entities

        for project in projects:
            ## get project level information
            project_key = project.get("key", "")
            project_name = project.get("name", "")
            project_url = f"{self.base_url}/project/overview?id={project_key}"

            ## fetch other information from API
            branches = await self.get_branches(client=client, project_key=project_key)
            project_quality_status = await self.get_quality_gate_status(client=client, project_key=project_key)
            quality_gate_name = await self.get_quality_gate_name(client=client, project_key=project_key)

            # Process the fetched data
            if branches and project_quality_status and quality_gate_name:

                quality_gate_onditions = project_quality_status.get("conditions", [])

                branch_name = branches.get("name", "")
                branch_type = branches.get("type", "")
                quality_gate_status = project_quality_status.get("status", "")

                quality_gates_data =  {
                    "server_url": self.base_url,
                    "project_key": project_key,
                    "project_name": project_name,
                    "project_url": project_url,
                    "branch_name": branch_name,
                    "branch_type": branch_type,
                    "quality_gate_name": quality_gate_name,
                    "quality_gate_status": quality_gate_status,
                    "quality_gate_conditions": quality_gate_onditions
                }
                all_quality_gates_data.append(quality_gates_data)
        
        return all_quality_gates_data

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