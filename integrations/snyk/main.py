from typing import Any
from enum import StrEnum
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.ocean import ocean
from snyk_integration.client import SnykClient


class ObjectKind(StrEnum):
    PROJECT = "projects"
    VULNERABILITY = "vulnerabilities"


snyk_client = SnykClient(
    ocean.integration_config["api_token"],
    ocean.integration_config["api_url"],
    ocean.integration_config["app_host"],
    ocean.integration_config["organization_id"],
    ocean.integration_config["webhook_secret"],
)


@ocean.on_resync(ObjectKind.PROJECT)
async def on_projects_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Snyk resource: {kind}")

    async for projects in snyk_client.get_paginated_projects():
        logger.info(f"Received batch with {len(projects)} projects")
        updated_project_users = await snyk_client.update_project_users(
            projects=projects
        )
        yield updated_project_users


@ocean.on_resync(ObjectKind.VULNERABILITY)
async def on_vulnerabilities_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Snyk resource: {kind}")
    async for project_data in snyk_client.get_paginated_projects():
        for project in project_data:
            async for vulnerabilities_data in snyk_client.get_vulnerabilities(project):
                yield vulnerabilities_data


@ocean.router.post("/webhook")
async def on_vulnerability_webhook_handler(data: dict[str, Any]) -> None:
    logger.info("Processing Snyk webhook event")

    project = data.get("project", {})
    project_details = await snyk_client.get_single_project(project)
    await ocean.register_raw(ObjectKind.PROJECT, [project_details])

    async for vulnerabilities_data in snyk_client.get_vulnerabilities(project):
        await ocean.register_raw(ObjectKind.VULNERABILITY, vulnerabilities_data)


@ocean.on_start()
async def on_start() -> None:
    ## check if user provided webhook secret or app_host. These variable are required to create webhook subscriptions. If the user did not provide them, we ignore creating webhook subscriptions
    if ocean.integration_config.get("app_host") and ocean.integration_config.get(
        "webhook_secret"
    ):
        logger.info("Subscribing to Snyk webhooks")
        await snyk_client.create_webhooks_if_not_exists()
