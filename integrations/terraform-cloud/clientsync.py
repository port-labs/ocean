import httpx
from typing import List, Dict,Any
from loguru import logger
from port_ocean.context.ocean import ocean



WEBHOOK_NAME = "Port-Ocean-Events-Webhook"
PAGE_SIZE = 100

TERRAFORM_WEBHOOK_EVENTS = ['run:applying',
                            'run:completed',
                            'run:created', 
                            'run:errored', 
                            'run:needs_attention', 
                            'run:planning',
                            "workspace:auto_destroy_run_results",
                            "workspace:auto_destro_reminder"]


class TerraformClient:
    def __init__(self, terraform_base_url: str, auth_token: str, organization: str) -> None:
        self.terraform_base_url = terraform_base_url
        self.auth_token = auth_token
        self.base_headers = {"Authorization": f"Bearer {self.auth_token}", "Content-Type": "application/vnd.api+json"}
        self.api_url = f"{self.terraform_base_url}/api/v2"
        self.organization = organization
        self.client = httpx.Client(headers=self.base_headers)

    def get_paginated_workspaces(self) -> List[Dict[str, any]]:
        per_page = 100
        page = 1

        logger.info("Getting workspaces from Terraform")
        while True:
            workspace_response = self.client.get(
                f"{self.api_url}/organizations/{self.organization}/workspaces?page[number]={page}&page[size]={per_page}"
            )
            workspace_response.raise_for_status()
            workspaces_data = workspace_response.json()
            workspaces = workspaces_data.get('data', [])
            logger.info(f"Got {len(workspaces)} workspaces from Terraform")
            yield workspaces

            if len(workspaces) < per_page:
                break
            page += 1

    async def get_single_workspace(self, workspace_id: str) -> Dict[str, Any]:
        try:

            logger.info(f"Getting details for run {workspace_id}")
            response = await self.client.get(f"{self.api_url}/workspaces/{workspace_id}")
            response.raise_for_status()
            return response.json().get('data', {})
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error with status code : {e.response.status_code} and response text: {e.response.text}")
        
        except httpx.HTTPError as e:
            logger.error(f"An error occured while fetching terraform data: {e}")

    def get_runs(self,workspace_id):

        run_response = self.client.get(
                f"{self.api_url}/workspaces/{workspace_id}/runs"
            )
        run_response.raise_for_status()
        runs_data = run_response.json()
        runs = runs_data.get('data', [])
        logger.info(f"Got {len(runs)} runs for workspace {workspace_id} from Terraform")

        detailed_runs = []
        for run in runs:
            run_id = run['id']
            run_details = self.get_run_details(run_id)
            detailed_runs.append(run_details)

        return detailed_runs
    
    def get_workspaces(self):
        
        try:
            logger.info(f"Getting all workspaces from terraform")
            workspace_response = self.client.get(f"{self.api_url}/organizations/{self.organization}/workspaces")
            workspace_response.raise_for_status()
            workspace_data = workspace_response.json()
            workspaces = workspace_data.get('data', [])
            
            workspace_ids = [workspace.get("id","") for workspace in workspaces]
            logger.info(f"Got {len(workspace_ids)} workspaces from terraform")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error with status code : {e.response.status_code} and response text: {e.response.text}")
        
        except httpx.HTTPError as e:
            logger.error(f"An error occured while fetching terraform data: {e}")

        

    def get_paginated_runs_for_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        per_page = 100
        page = 1

        logger.info(f"Getting runs for workspace {workspace_id} from Terraform")
        
        while True:
            run_response = self.client.get(
                f"{self.api_url}/workspaces/{workspace_id}/runs?page[number]={page}&page[size]={per_page}"
            )
            run_response.raise_for_status()
            runs_data = run_response.json()
            runs = runs_data.get('data', [])
            logger.info(f"Got {len(runs)} runs for workspace {workspace_id} from Terraform on page {page}")

            detailed_runs = []
            for run in runs:
                run_id = run['id']
                run_details = self.get_run_details(run_id)
                detailed_runs.append(run_details)

            yield detailed_runs

            if len(runs) < per_page:
                break
            page += 1

    def create_workspace_webhook(self, workspace_id: str,app_host:str) -> None:
        webhook_target_url = app_host #"https://ingest.getport.io/ueHJReOgPGyfLFyQ"
        notification_config_url = f"{self.api_url}/workspaces/{workspace_id}/notification-configurations"

        # Check existing webhook configurations
        existing_configs_response = self.client.get(notification_config_url)
        existing_configs_response.raise_for_status()
        existing_configs = existing_configs_response.json()

        for config in existing_configs.get('data', []):          
            if config.get('attributes', {}).get('url', '') == webhook_target_url:
                logger.info("Webhook already exists for this workspace")
                return

        # Create new webhook configuration
        webhook_body = {
            "data": {
                "type": "notification-configurations",  # Ensure this is the correct type
                "attributes": {
                    "destination-type": "generic",  # Confirm this is a valid destination type
                    "enabled": True,
                    "name": "port integration webhook",
                    "url": webhook_target_url,  # Make sure this is the correct URL
                    "triggers": TERRAFORM_WEBHOOK_EVENTS  # Confirm these events are valid for Terraform
                }
            }
        }

        

        webhook_create_response = self.client.post(notification_config_url, json=webhook_body)
        webhook_create_response.raise_for_status()
        logger.info(f"Ocean real time webhook created for Terraform workspace - {workspace_id}")


    def get_run_details(self, run_id: str) -> Dict[str, Any]:
        logger.info(f"Getting details for run {run_id}")
        details_response = self.client.get(f"{self.api_url}/runs/{run_id}")
        details_response.raise_for_status()
        return details_response.json().get('data', {})
    

    def get_state_version_output_for_workspace(self) -> List[Dict[str, Any]]:
        try:

            for workspaces in self.get_paginated_workspaces():
                for workspace in workspaces:
                    workspace_name = workspace['attributes']['name']
                    page = 1

                    logger.info(f"Getting state version outputs for workspace {workspace_name}")
                    while True:

                        state_versions_url = f"{self.api_url}/state-versions?page[number]={page}&page[size]={PAGE_SIZE}&filter[workspace][name]={workspace_name}&filter[organization][name]={self.organization}"
                        response = self.client.get(state_versions_url)
                        response.raise_for_status()
                        state_versions_data = response.json()
                        state_versions = state_versions_data.get('data', [])
                        yield state_versions

                        if len(state_versions) < PAGE_SIZE:
                            break
                        page += 1

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for state versions: Status {e.response.status_code}, Response: {e.response.text}")
        except httpx.HTTPError as e:
            logger.error(f"Error fetching state versions: {e}")







    # async def create_workspace_webhook(self,app_host:str) -> None:

    #     try:

    #         webhook_target_url = f"{app_host}"#/integration/webhook"

    #         async for workspaces in self.get_paginated_workspaces():

    #             for workspace in workspaces:

    #                 notification_config_url = f"{self.api_url}/workspaces/{workspace['id']}/notification-configurations"
    #                 print(notification_config_url)

    #                 # Check existing webhook configurations
    #                 existing_configs_response = await self.client.get(notification_config_url)
    #                 existing_configs_response.raise_for_status()
    #                 existing_configs = existing_configs_response.json().get('data', [])

    #                 print(existing_configs)

    #                 skip = 0
    #                 if existing_configs:
    #                     for config in existing_configs:          
    #                         if config['attributes']['url'] == webhook_target_url:
    #                             logger.info(f"Webhook already exists for this workspace - {workspace['id']}")
    #                             skip = 1
    #                             break
    #                 if skip:
    #                     continue

    #                 # Create new webhook configuration
    #                 webhook_body = {
    #                     "data": {
    #                         "type": "notification-configurations",
    #                         "attributes": {
    #                             "destination-type": "generic", 
    #                             "enabled": True,
    #                             "name": "port integration webhook",
    #                             "url": webhook_target_url,
    #                             "triggers": TERRAFORM_WEBHOOK_EVENTS
    #                         }
    #                     }
    #                 }

    #                 webhook_create_response = await self.client.post(notification_config_url, json=webhook_body)
    #                 webhook_create_response.raise_for_status()
    #                 logger.info(f"Ocean real time webhook created for Terraform workspace - {workspace['id']}")
        
    #     except httpx.HTTPStatusError as e:
    #         logger.error(f"HTTP error with status code : {e.response.status_code} and response text: {e.response.text}")
        
    #     except httpx.HTTPError as e:
    #         logger.error(f"An error occured while fetching terraform data: {e}")




if __name__ == "__main__":
    TERRAFORM_TOKEN = "rGeNA5YzQIw5Jw.atlasv1.Zgh1XeEdkT06IsA8kprXWKpz56VMqW0Xp1O5AATBS7Zzy4iiNQbQVNX46TmfkNQdw0U"
    TERRAFORM_ORGANIZATION = "example-org-162af6"
    terraform_client = TerraformClient("https://app.terraform.io", TERRAFORM_TOKEN, TERRAFORM_ORGANIZATION)
    output = terraform_client.get_state_version_output_for_workspace()
    for i in output:
        print(i)
        print("\n\n Next")


    # for workspaces in terraform_client.get_paginated_workspaces():
    #     for workspace in workspaces:
    #         workspace_name = workspace['attributes']['name']
    #         print(workspace_name)
    #         workspace_version_outputs = terraform_client.get_state_version_output_for_workspace(workspace_name)
    #         print(workspace_version_outputs)



    # workspace_ids = terraform_client.get_workspaces()
    # print(workspace_ids)






# @ocean.on_resync(ObjectKind.RUN)
# async def resync_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
#     terraform_client = init_terraform_client()

#     async for workspaces in terraform_client.get_paginated_workspaces():
#         logger.info(f"Received ${len(workspace)} batch runs")
#         for workspace in workspaces:
#             runs = await terraform_client.get_runs(workspace['id'])
#             yield runs