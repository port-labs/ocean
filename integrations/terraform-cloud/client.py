import httpx
from typing import List, Dict, Any, AsyncGenerator
from loguru import logger
from port_ocean.context.event import event
from enum import StrEnum


TERRAFORM_WEBHOOK_EVENTS = ['run:applying',
                            'run:completed',
                            'run:created', 
                            'run:errored', 
                            'run:needs_attention',
                            'run:planning']

class CacheKeys(StrEnum):
    WORKSPACES = "workspace"
    RUNS = "run"
    STATE_VERSION_OUTPUTS = "state-version-output"
    STATE_VERSION = "state-version"


PAGE_SIZE = 100

class TerraformClient:

    def __init__(self, terraform_base_url: str, auth_token: str) -> None:
        self.terraform_base_url = terraform_base_url
        self.base_headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/vnd.api+json"}
        self.api_url = f"{self.terraform_base_url}/api/v2"
        self.client = httpx.AsyncClient(headers=self.base_headers)


    async def build_api_url(self, endpoint: str, workspace_id: str = None, page: int = 1, organization_id: str = None) -> str:
        url = f"{self.api_url}/{endpoint}"
        params = {"page[number]": page, "page[size]": PAGE_SIZE}
        if workspace_id:
            params["filter[workspace][name]"] = workspace_id
        if organization_id:
            params["filter[organization][name]"] = organization_id
        return f"{url}?{httpx.QueryParams(params)}"
    
    
    async def get_single_workspace(self, workspace_id: str) -> Dict[str, Any]:
        
        try:
            workspace_url = f"{self.api_url}/workspaces/{workspace_id}"
            response = await self.client.get(workspace_url)
            response.raise_for_status()
            return response.json().get('data', {})
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error with status code : {e.response.status_code} and response text: {e.response.text}")
        
        except httpx.HTTPError as e:
            logger.error(f"An error occured while fetching terraform data: {e}")


    async def get_paginated_workspaces(self) -> List[Dict[str, any]]:

        all_workspaces = []

        try:        
            page = 1

            logger.info("Getting workspaces from Terraform")
            while True:

                async for organization in self.get_organizations():

                    url = await self.build_api_url(endpoint= f"organizations/{organization[id]}",page=page)
                    workspace_response = await self.client.get(
                        # f"{self.api_url}/organizations/{organization['id']}/workspaces?page[number]={page}&page[size]={PAGE_SIZE}"
                        url
                    )
                    workspace_response.raise_for_status()
                    workspaces_data = workspace_response.json()
                    workspaces = workspaces_data.get('data', [])

                    yield workspaces

                    if len(workspaces) < PAGE_SIZE:
                        break

                    page += 1
                    all_workspaces.extend(workspaces)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error with status code : {e.response.status_code} and response text: {e.response.text}")
        
        except httpx.HTTPError as e:
            logger.error(f"An error occured while fetching terraform data: {e}")
    

    async def get_paginated_runs_for_workspace(self, workspace_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        
        try:
            page = 1

            logger.info(f"Getting runs for workspace {workspace_id} from Terraform")
            while True:
                url = await self.build_api_url(endpoint=f"workspaces/{workspace_id}/runs",
                                               page=page 
                                               )
                
                run_response = await self.client.get(
                    # f"{self.api_url}/workspaces/{workspace_id}/runs?page[number]={page}&page[size]={PAGE_SIZE}"
                    url
                )
                run_response.raise_for_status()
                runs_data = run_response.json()
                runs = runs_data.get('data', [])
                yield runs

                if len(runs) < PAGE_SIZE:
                    break
                page += 1

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error with status code : {e.response.status_code} and response text: {e.response.text}")
        
        except httpx.HTTPError as e:
            logger.error(f"An error occured while fetching terraform data: {e}")


    async def get_single_run(self, run_id: str) -> Dict[str, Any]:
        try:
            run_url = f"{self.api_url}/runs/{run_id}"
            response = await self.client.get(run_url)
            response.raise_for_status()
            return response.json().get('data', {})
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error with status code : {e.response.status_code} and response text: {e.response.text}")
        
        except httpx.HTTPError as e:
            logger.error(f"An error occured while fetching terraform data: {e}")


    async def create_workspace_webhook(self, app_host: str) -> None:
        try:
            webhook_target_url = f"{app_host}/integration/webhook"

            async for workspaces in self.get_paginated_workspaces():
                for workspace in workspaces:
                    notification_config_url = f"{self.api_url}/workspaces/{workspace['id']}/notification-configurations"

                    existing_configs_response = await self.client.get(notification_config_url)
                    existing_configs_response.raise_for_status()
                    existing_configs = existing_configs_response.json().get('data', [])

                    for config in existing_configs:
                        if config['attributes']['url'] == webhook_target_url:
                            logger.info(f"Webhook already exists for workspace {workspace['id']}")
                            break

                    else:
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
                        logger.info(f"Webhook created for Terraform workspace {workspace['id']}")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for workspace {workspace.get('id', 'unknown')}: Status {e.response.status_code}, Response: {e.response.text}")
        except httpx.HTTPError as e:
            logger.error(f"Error fetching Terraform data: {e}")


    async def get_state_version_for_workspace(self) -> AsyncGenerator[Dict[str, Any], None]:
        try:

            cache_key = CacheKeys.STATE_VERSION

            if cache := event.attributes.get(cache_key):
                logger.info("Fetching paginated workspaces from cache")
                yield cache
                return

            logger.info("Getting state versions for all workspaces")

            async for workspaces in self.get_paginated_workspaces():

                for workspace in workspaces:
                    workspace_name = workspace['attributes']['name']
                    organization_id = workspace['relationships']['data']['id']
                    page = 1

                    all_state_versions = []
                    while True:              
                        
                        url = self.build_api_url("state-versions",
                                                 page=page,
                                                 workspace_id=workspace_name,
                                                 organization_id=organization_id)
                        
                        # state_versions_url = f"{self.api_url}/state-versions?page[number]={page}&page[size]={PAGE_SIZE}&filter[workspace][name]={workspace_name}&filter[organization][name]={organization_id}"
                        response = await self.client.get(url)
                        response.raise_for_status()
                        state_versions_data = response.json()
                        state_versions = state_versions_data.get('data', [])
                        yield state_versions

                        if len(state_versions) < PAGE_SIZE:
                            break

                        page += 1

                        all_state_versions.extend(workspaces)

                    event.attributes[cache_key] = all_state_versions

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for state versions: Status {e.response.status_code}, Response: {e.response.text}")
        except httpx.HTTPError as e:
            logger.error(f"Error fetching terraform data: {e}")



    async def get_organizations(self)-> List[Dict[str, Any], None]:
        
        try:
            logger.info("Getting organizations from terraform")

            organizations_url = f"{self.api_url}/organizations"
            response = await self.client.get(organizations_url)
            response.raise_for_status()
            organizations_data = response.json()
            organizations = organizations_data.get('data', [])
            return organizations

        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for state versions: Status {e.response.status_code}, Response: {e.response.text}")
        except httpx.HTTPError as e:
            logger.error(f"Error fetching terraform data: {e}")

        

    async def get_state_version_outputs_for_workspace(self)-> AsyncGenerator[Dict[str, Any], None]:
        try:

            page = 1
            while True:

                async for state_versions in self.get_state_version_for_workspace():
                    for state_version in state_versions:
                        logger.info("Getting state version outputs for all workspaces")
                        #state_version_outputs_url = f"{self.api_url}/state-versions/{state_version['id']}/outputs?page[number]={page}&page[size]={PAGE_SIZE}"
                        url = self.build_api_url(endpoint= f"state-versions/{state_version['id']}/outputs",page=page)
                        response = await self.client.get(url)
                        response.raise_for_status()
                        state_version_outputs_data = response.json()
                        state_version_outputs = state_version_outputs_data.get('data', [])

                        for state_version_output in state_version_outputs:
                            state_version_output['__stateVersion'] = state_version

                        yield state_version_outputs

                        if len(state_version_outputs) < PAGE_SIZE:
                            break
                        page += 1
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for state versions: Status {e.response.status_code}, Response: {e.response.text}")
        except httpx.HTTPError as e:
            logger.error(f"Error fetching terraform data: {e}")


    async def get_terraform_data(self,url):
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            response_json = response.json()
            response_data = response_json.get('data', [])
            return response_data
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for state versions: Status {e.response.status_code}, Response: {e.response.text}")
        except httpx.HTTPError as e:
            logger.error(f"Error fetching terraform data: {e}")
