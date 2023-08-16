from typing import Any
from enum import StrEnum
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.ocean import ocean
from snyk_integration.client import SnykClient


class ObjectKind(StrEnum):
    TARGET = "targets"
    PROJECT = "projects"
    VULNERABILITY = "vulnerabilities"


snyk_client = SnykClient(
    ocean.integration_config["api_token"],
    ocean.integration_config["api_url"],
    ocean.integration_config["app_host"],
    ocean.integration_config["organization_id"],
    ocean.integration_config["webhook_secret"],
)


@ocean.on_resync(ObjectKind.TARGET)
async def on_targets_resync(kind: str) -> list[dict[Any, Any]]:
    logger.info(f"Listing Snyk resource: {kind}")
    targets = await snyk_client.get_targets()
    return targets


@ocean.on_resync(ObjectKind.PROJECT)
async def on_projects_resync(kind: str) -> list[dict[Any, Any]]:
    logger.info(f"Listing Snyk resource: {kind}")
    return await snyk_client.get_projects()


@ocean.on_resync(ObjectKind.VULNERABILITY)
async def on_vulnerabilities_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Snyk resource: {kind}")
    projects = await snyk_client.get_projects()
    for project in projects:
        vulnerabilities_data = await snyk_client.get_vulnerabilities(project)
        yield vulnerabilities_data


@ocean.router.post("/webhook")
async def on_vulnerability_webhook_handler(data: dict[str, Any]) -> None:
    logger.info("Processing Snyk webhook event")

    project = data.get("project", {})
    vulnerabilities = await snyk_client.get_vulnerabilities(project)
    await ocean.register_raw(ObjectKind.VULNERABILITY, vulnerabilities)


@ocean.on_start()
async def on_start() -> None:
    logger.info("Subscribing to Snyk webhooks")
    await snyk_client.create_webhooks_if_not_exists()
