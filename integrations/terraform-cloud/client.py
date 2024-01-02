from typing import Any, AsyncGenerator, Optional
from port_ocean.utils import http_async_client
import httpx
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
        self.client = http_async_client
        self.client.headers.update(self.base_headers)

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        logger.info(f"Requesting Terraform Cloud data for endpoint: {endpoint}")
        try:
            url = f"{self.api_url}/{endpoint}"
            logger.info(
                f"URL: {url}, Method: {method}, Params: {query_params}, Body: {json_data}"
            )
            response = await self.client.request(
                method=method,
                url=url,
                params=query_params,
                json=json_data,
            )
            response.raise_for_status()

            logger.info(f"Successfully retrieved data for endpoint: {endpoint}")

            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error on {endpoint}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error on {endpoint}: {str(e)}")
            raise

    async def get_paginated_resources(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = params or {}
        params.update({"page[size]": PAGE_SIZE})
        next_url = endpoint

        while next_url:
            response = await self.send_api_request(
                endpoint=next_url, query_params=params
            )
            resources = response.get("data", [])

            pagination_meta = response.get("meta", {}).get("pagination", {})

            current_page = pagination_meta.get("current-page", "Unknown")
            total_pages = pagination_meta.get("total-pages", "Unknown")
            total_count = pagination_meta.get("total-count", "Unknown")

            logger.info(
                f"Fetched {total_count} resources from {next_url} - Page {current_page} of {total_pages}... "
            )
            yield resources

            next_url = response.get("links", {}).get("next", "")
            if not next_url:
                logger.info(f"No more pages to fetch for {endpoint}")
                break

            next_url = next_url.replace(self.api_url + "/", "")
            params = None

    async def get_paginated_organizations(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Fetching organizations")
        async for organizations in self.get_paginated_resources("organizations"):
            yield organizations

    async def get_single_workspace(self, workspace_id: str) -> dict[str, Any]:
        logger.info(f"Fetching workspace with ID: {workspace_id}")
        workspace = await self.send_api_request(endpoint=f"workspaces/{workspace_id}")
        return workspace.get("data", {})

    async def get_single_run(self, run_id: str) -> dict[str, Any]:
        logger.info(f"Fetching run with ID: {run_id}")
        run = await self.send_api_request(endpoint=f"runs/{run_id}")
        return run.get("data", {})

    async def get_state_version_output(self, state_version_id: str) -> dict[str, Any]:
        logger.info(f"Fetching state version output for ID: {state_version_id}")
        outputs = await self.send_api_request(
            endpoint=f"state-versions/{state_version_id}/outputs"
        )
        return outputs.get("data", {})

    async def get_paginated_workspaces(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        cache_key = "terraform-cloud-workspace"
        if cache := event.attributes.get(cache_key):
            logger.info("Retrieving workspaces data from cache")
            yield cache
            return

        all_workspaces = []
        logger.info("Starting to fetch workspaces across all organizations")
        async for organizations in self.get_paginated_organizations():
            for organization in organizations:
                organization_id = organization["id"]
                logger.info(
                    f"Fetching workspaces for organization ID: {organization_id}"
                )
                endpoint = f"organizations/{organization_id}/workspaces"
                async for workspaces in self.get_paginated_resources(endpoint):
                    num_workspaces = len(workspaces)
                    logger.info(
                        f"Retrieved {num_workspaces} workspaces for organization ID: {organization_id}"
                    )
                    all_workspaces.extend(workspaces)
                    yield workspaces

        event.attributes[cache_key] = workspaces
        logger.info(
            f"Total workspaces retrieved across all organizations: {len(all_workspaces)}"
        )

    async def get_paginated_projects(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Starting to fetch projects across all organizations")
        async for organizations in self.get_paginated_organizations():
            for organization in organizations:
                organization_id = organization["id"]
                logger.info(f"Fetching projects for organization ID: {organization_id}")
                endpoint = f"/organizations/{organization_id}/projects"
                async for projects in self.get_paginated_resources(endpoint):
                    num_projects = len(projects)
                    logger.info(
                        f"Retrieved {num_projects} projects for organization ID: {organization_id}"
                    )

                    yield projects

    async def get_paginated_runs_for_workspace(
        self, workspace_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(f"Fetching runs for workspace ID: {workspace_id}")

        endpoint = f"workspaces/{workspace_id}/runs"

        async for runs in self.get_paginated_resources(endpoint):
            yield runs

    async def get_paginated_state_versions(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for workspaces in self.get_paginated_workspaces():
            for workspace in workspaces:
                workspace_name = workspace["attributes"]["name"]
                organization_name = workspace["relationships"]["organization"]["data"][
                    "id"
                ]

                logger.info(f"Fetching state versions for workspace {workspace_name}")
                filter_params = {
                    "filter[workspace][name]": workspace_name,
                    "filter[organization][name]": organization_name,
                }

                async for state_versions in self.get_paginated_resources(
                    "state-versions", filter_params
                ):
                    yield state_versions

    async def create_workspace_webhook(self, app_host: str) -> None:
        webhook_target_url = f"{app_host}/integration/webhook"
        async for workspaces in self.get_paginated_workspaces():
            for workspace in workspaces:
                workspace_id = workspace["id"]
                endpoint = f"workspaces/{workspace_id}/notification-configurations"
                notifications_response = await self.send_api_request(endpoint=endpoint)
                existing_configs = notifications_response.get("data", [])

                webhook_exists = any(
                    config["attributes"]["url"] == webhook_target_url
                    for config in existing_configs
                )
                if webhook_exists:
                    logger.info(f"Webhook already exists for workspace {workspace_id}")
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
                    await self.send_api_request(
                        endpoint=endpoint, method="POST", json_data=webhook_body
                    )
                    logger.info(
                        f"Webhook created for Terraform workspace {workspace_id}"
                    )
