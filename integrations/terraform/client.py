# from port_ocean.utils import http_async_client as httpx
import httpx
from typing import List, Dict, Any, AsyncGenerator
from loguru import logger


TERRAFORM_WEBHOOK_EVENTS = [
    "run:created",
    "run:planning",
    "jira:issue_deleted",
    "run:needs_attention",
    "run:applying",
    "run:completed",
    "run:errored",
    "assessment:drifted",
    "assessment:failed",
    "workspace:auto_destro_reminder",
    "workspace:auto_destroy_run_results"
]


class TerraformClient:

    def __init__(self, terraform_base_url: str, auth_token: str, organization: str) -> None:
        self.terraform_base_url = terraform_base_url
        self.auth_token = auth_token
        self.base_headers = {"Authorization": f"Bearer {self.auth_token}", "Content-Type": "application/vnd.api+json"}
        self.api_url = f"{self.terraform_base_url}/api/v2"
        self.organization = organization
        self.client = httpx.AsyncClient(headers=self.base_headers)

    async def get_paginated_workspaces(self) -> List[Dict[str, any]]:

        try:        
            per_page = 100
            page = 1

            logger.info("Getting workspaces from Terraform")
            while True:
                workspace_response = await self.client.get(
                    f"{self.api_url}/organizations/{self.organization}/workspaces?page[number]={page}&page[size]={per_page}"
                )
                workspace_response.raise_for_status()
                workspaces_data = workspace_response.json()
                workspaces = workspaces_data.get('data', [])
                yield workspaces

                if len(workspaces) < per_page:
                    break
                page += 1

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error with status code : {e.response.status_code} and response text: {e.response.text}")
        
        except httpx.HTTPError as e:
            logger.error(f"An error occured while fetching terraform data: {e}")


    async def get_paginated_runs_for_workspace(self, workspace_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        
        try:
            per_page = 100
            page = 1

            logger.info(f"Getting runs for workspace {workspace_id} from Terraform")
            while True:
                run_response = await self.client.get(
                    f"{self.api_url}/workspaces/{workspace_id}/runs?page[number]={page}&page[size]={per_page}"
                )
                run_response.raise_for_status()
                runs_data = run_response.json()
                runs = runs_data.get('data', [])
                print(runs)
                yield runs

                if len(runs) < per_page:
                    break
                page += 1

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error with status code : {e.response.status_code} and response text: {e.response.text}")
        
        except httpx.HTTPError as e:
            logger.error(f"An error occured while fetching terraform data: {e}")


    async def create_workspace_webhook(self,app_host:str) -> None:

        try:

            webhook_target_url = app_host

            async for workspaces in self.get_paginated_workspaces():

                for workspace in workspaces:

                    notification_config_url = f"{self.api_url}/workspaces/{workspace['id']}/notification-configurations"

                    # Check existing webhook configurations
                    existing_configs_response = await self.client.get(notification_config_url)
                    existing_configs_response.raise_for_status()
                    existing_configs = existing_configs_response.json()

                    for config in existing_configs.get('data', []):          
                        if config.get('attributes', {}).get('url', '') == webhook_target_url:
                            logger.info("Webhook already exists for this workspace")
                            return

                    # Create new webhook configuration
                    webhook_body = {
                        "data": {
                            "type": "notification-configurations",
                            "attributes": {
                                "destination-type": "generic", 
                                "enabled": True,
                                "name": "port integration webhook",
                                "url": webhook_target_url,
                                "triggers": TERRAFORM_WEBHOOK_EVENTS
                            }
                        }
                    }

                    webhook_create_response = await self.client.post(notification_config_url, json=webhook_body)
                    webhook_create_response.raise_for_status()
                    logger.info(f"Ocean real time webhook created for Terraform workspace - {workspace['id']}")
        
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error with status code : {e.response.status_code} and response text: {e.response.text}")
        
        except httpx.HTTPError as e:
            logger.error(f"An error occured while fetching terraform data: {e}")
