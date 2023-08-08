from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from sonarqube_integration.sonarqube_client import SonarQubeClient
import httpx

# Initialize the SonarQubeClient instance
sonar_client = SonarQubeClient(
    ocean.integration_config["sonar_url"],
    ocean.integration_config["sonar_api_token"],
    ocean.integration_config["sonar_organization_id"],
    ocean.integration_config["app_host"],
    httpx.AsyncClient(),
)


@ocean.on_resync("cloudAnalysis")
async def on_cloud_analysis_resync(kind: str) -> list[dict[str, Any]]:
    logger.info(f"Listing Sonarqube resource: {kind}")
    quality_analysis = await sonar_client.get_sonarqube_cloud_analysis()
    return quality_analysis


@ocean.router.post("/webhook")
async def handle_sonarqube_webhook(data: dict[str, Any]) -> None:
    logger.info(
        f"Processing Sonarqube webhook for event type: {data['project']['key']}"
    )

    project = data.get("project", {})
    quality_analysis = await sonar_client.get_cloud_analysis_data_for_project(project)
    await ocean.register_raw("cloudAnalysis", [quality_analysis])


@ocean.on_start()
async def on_start() -> None:
    await sonar_client.get_or_create_webhook_url()