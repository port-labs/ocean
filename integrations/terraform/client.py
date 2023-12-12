import httpx
from typing import List, Dict, Any, AsyncGenerator
from loguru import logger


class TerraformClient:
    def __init__(self, terraform_base_url: str, auth_token: str, organization: str) -> None:
        self.terraform_base_url = terraform_base_url
        self.auth_token = auth_token
        self.base_headers = {"Authorization": f"Bearer {self.auth_token}", "Content-Type": "application/vnd.api+json"}
        self.api_url = f"{self.terraform_base_url}/api/v2"
        self.organization = organization
        self.client = httpx.AsyncClient(headers=self.base_headers)

    async def get_paginated_workspaces(self) -> List[Dict[str, any]]:
        per_page = 100
        page = 1
        all_workspaces = []

        logger.info("Getting workspaces from Terraform")
        while True:
            workspace_response = await self.client.get(
                f"{self.api_url}/organizations/{self.organization}/workspaces?page[number]={page}&page[size]={per_page}"
            )
            workspace_response.raise_for_status()
            workspaces_data = workspace_response.json()
            workspaces = workspaces_data.get('data', [])
            all_workspaces.extend(workspaces)
            logger.info(f"Got {len(workspaces)} workspaces from Terraform")
            yield workspaces

            if len(workspaces) < per_page:
                break
            page += 1


    async def get_paginated_runs_for_workspace(self, workspace_id: str) -> AsyncGenerator[Dict[str, Any], None]:
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
            logger.info(f"Got {len(runs)} runs for workspace {workspace_id} from Terraform on page {page}")

            detailed_runs = []
            for run in runs:
                run_id = run['id']
                run_details = await self.get_run_details(run_id)
                detailed_runs.append(run_details)

            yield detailed_runs

            if len(runs) < per_page:
                break
            page += 1



    async def get_runs(self,workspace_id):

        run_response = await self.client.get(
                f"{self.api_url}/workspaces/{workspace_id}/runs"
            )
        run_response.raise_for_status()
        runs_data = run_response.json()
        runs = runs_data.get('data', [])
        logger.info(f"Got {len(runs)} runs for workspace {workspace_id} from Terraform on page {page}")

        detailed_runs = []
        for run in runs:
            run_id = run['id']
            run_details = await self.get_run_details(run_id)
            detailed_runs.append(run_details)

        return detailed_runs



    async def get_run_details(self, run_id: str) -> Dict[str, Any]:
        logger.info(f"Getting details for run {run_id}")
        details_response = await self.client.get(f"{self.api_url}/runs/{run_id}")
        details_response.raise_for_status()
        return details_response.json().get('data', {})
