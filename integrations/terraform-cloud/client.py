import httpx
from typing import Any, AsyncGenerator, Optional
from loguru import logger
from port_ocean.context.event import event

TERRAFORM_WEBHOOK_EVENTS = [
    "run:applying",
    "run:completed",
    "run:created",
    "run:errored",
    "run:needs_attention",
    "run:planning",
]


PAGE_SIZE = 100


class TerraformClient:
    def __init__(self, terraform_base_url: str, auth_token: str) -> None:
        self.terraform_base_url = terraform_base_url
        self.base_headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/vnd.api+json",
        }
        self.api_url = f"{self.terraform_base_url}/api/v2"
        self.client = httpx.AsyncClient(headers=self.base_headers)

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        logger.info(f"Requesting Terraform Cloud data for endpoint: {endpoint}")
        try:
            response = await self.client.request(
                method=method,
                url=f"{self.api_url}/{endpoint}",
                params=query_params,
                json=json_data,
            )
            response.raise_for_status()

            logger.info(
                f"Successfully retrieved Terraform Cloud data for endpoint: {endpoint}"
            )

            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

        except httpx.HTTPError:
            logger.exception("An error occured while fetching terraform cloud data")
            raise

    async def get_organizations(self) -> list[dict[str, Any]]:
        response = await self.send_api_request(endpoint="organizations")
        return response.get("data", [])

    async def get_single_workspace(self, workspace_id: str) -> dict[str, Any]:
        response = await self.send_api_request(endpoint=f"workspaces/{workspace_id}")
        return response.get("data", {})

    async def get_single_run(self, run_id: str) -> dict[str, Any]:
        response = await self.send_api_request(endpoint=f"runs/{run_id}")
        return response.get("data", {})

    async def get_state_version_output(self, state_version_id: str) -> dict[str, Any]:
        response = await self.send_api_request(
            endpoint=f"state-versions/{state_version_id}/outputs"
        )
        return response.get("data", {})

    async def get_paginated_workspaces(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        
        logger.info("Starting to fetch workspaces...")
        cache_key = "terraform-cloud-workspace"
        if cache := event.attributes.get(cache_key):
            logger.info("Retrieving workspaces data from cache")
            yield cache
            return

        page = 1
        all_workspaces = []
        organizations = await self.get_organizations()
        for organization in organizations:
            logger.info(f"Getting workspaces for {organization['id']}")

            while True:
                params: dict[str, Any] = {"page[number]": page, "page[size]": PAGE_SIZE}
                response = await self.send_api_request(
                    endpoint=f"organizations/{organization['id']}/workspaces",
                    query_params=params,
                )
                workspaces = response.get("data", [])
                all_workspaces.extend(workspaces)
                logger.info(f"Fetched {len(workspaces)} workspaces for organization {organization['id']} on page {page}")

                yield workspaces

                if len(workspaces) < PAGE_SIZE:
                    logger.debug("No more workspaces to fetch for this organization")
                    break

                page += 1
        event.attributes[cache_key] = all_workspaces
        logger.info("Successfully retrieved workspaces for all organizations")

    async def get_paginated_runs_for_workspace(
        self, workspace_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(f"Getting runs for workspace {workspace_id} from Terraform")

        page = 1
        while True:
            params: dict[str, Any] = {"page[number]": page, "page[size]": PAGE_SIZE}

            logger.debug(f"Fetching page {page} of runs for workspace: {workspace_id}")
            response = await self.send_api_request(
                endpoint=f"workspaces/{workspace_id}/runs", query_params=params
            )
            runs = response.get("data", [])
            logger.info(f"Recieved {len(runs)} runs for workspace: {workspace_id} on page {page}")
            yield runs

            if len(runs) < PAGE_SIZE:
                logger.debug(f"No more runs to fetch for workspace: {workspace_id} after page {page}")
                break
            page += 1

        logger.info(f"Completed fetching all runs for workspace: {workspace_id}")

    async def get_paginated_state_version(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting state versions for all workspaces")

        async for workspaces in self.get_paginated_workspaces():
            for workspace in workspaces:
                page = 1

                while True:
                    params: dict[str, Any] = {
                        "page[number]": page,
                        "page[size]": PAGE_SIZE,
                        "filter[workspace][name]": workspace["attributes"]["name"],
                        "filter[organization][name]": workspace["relationships"][
                            "organization"
                        ]["data"]["id"],
                    }
                    response = await self.send_api_request(
                        endpoint="state-versions", query_params=params
                    )
                    state_versions = response.get("data", [])
                    logger.info(f"Received {len(state_versions)} state versions for workspace {workspace['id']} on page {page}")
                    yield state_versions

                    if len(state_versions) < PAGE_SIZE:
                        logger.debug("No more state versions to fetch for workspace")
                        break

                    page += 1
        logger.info("Successfully retrieved state versions for all workspaces")

    async def create_workspace_webhook(self, app_host: str) -> None:
        webhook_target_url = f"{app_host}/integration/webhook"

        async for workspaces in self.get_paginated_workspaces():
            for workspace in workspaces:
                notification_config_url = f"{self.api_url}/workspaces/{workspace['id']}/notification-configurations"
                logger.debug(f"Fetching existing webhooks for workspace {workspace['id']}")
                
                notifications_response = await self.send_api_request(
                    endpoint=notification_config_url
                )
                existing_configs = notifications_response.get("data", [])

                for config in existing_configs:
                    if config["attributes"]["url"] == webhook_target_url:
                        logger.info(
                            f"Skipping webhook creation: Webhook already exists for workspace {workspace['id']}"
                        )
                    
                    else:
                        webhook_body = {
                            "data": {
                                "type": "notification-configurations",
                                "attributes": {
                                    "destination-type": "generic",
                                    "enabled": True,
                                    "name": "port integration webhook",
                                    "url": webhook_target_url,
                                    "triggers": TERRAFORM_WEBHOOK_EVENTS,
                                },
                            }
                        }

                        logger.debug(f"Creating new webhook for workspace {workspace['id']}")

                        await self.send_api_request(
                            endpoint=notification_config_url,
                            method="POST",
                            json_data=webhook_body,
                        )
                        logger.info(
                            f"Webhook created for Terraform workspace {workspace['id']}"
                        )

        logger.info("Completed webhook creation process for all workspaces")