from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from sonarqube_integration.sonarqube_client import SonarQubeClient
import httpx


class ObjectKind:
    PROJECTS = "projects"
    QUALITY_GATES = "qualitygates"


# Initialize the SonarQubeClient instance
sonar_client = SonarQubeClient(
    ocean.integration_config["sonar_url"],
    ocean.integration_config["sonar_api_token"],
    ocean.integration_config["sonar_organization_id"],
    ocean.integration_config["app_host"],
    httpx.AsyncClient(),
)


@ocean.on_resync(ObjectKind.PROJECTS)
async def on_project_resync(kind: str) -> list[dict[str, Any]]:
    logger.info(f"Listing Sonarqube resource: {kind}")
    return await sonar_client.get_projects()


@ocean.on_resync(ObjectKind.QUALITY_GATES)
async def on_quality_gate_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Sonarqube resource: {kind}")
    projects = await sonar_client.get_projects()
    for project in projects:
        quality_gate = await sonar_client.get_cloud_analysis_data_for_project(project)
        yield quality_gate


@ocean.router.post("/webhook")
async def handle_sonarqube_webhook(data: dict[str, Any]) -> None:
    logger.info(
        f"Processing Sonarqube webhook for event type: {data['project']['key']}"
    )

    project = data.get("project", {})
    quality_analysis = await sonar_client.get_cloud_analysis_data_for_project(project)
    await ocean.register_raw(ObjectKind.QUALITY_GATES, [quality_analysis])


@ocean.on_start()
async def on_start() -> None:
    await sonar_client.get_or_create_webhook_url()
