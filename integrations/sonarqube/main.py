from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from sonarqube_integration.sonarqube_client import SonarQubeClient
import httpx


class ObjectKind:
    PROJECTS = "projects"
    ISSUES = "issues"
    ANALYSIS = "analysis"


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


@ocean.on_resync(ObjectKind.ISSUES)
async def on_issues_resync(kind: str) -> list[dict[str, Any]]:
    logger.info(f"Listing Sonarqube resource: {kind}")
    components = await sonar_client.get_components()
    return await sonar_client.get_issues(components)


@ocean.on_resync(ObjectKind.ANALYSIS)
async def on_analysis_resync(kind: str) -> list[dict[str, Any]]:
    logger.info(f"Listing Sonarqube resource: {kind}")
    components = await sonar_client.get_components()
    return await sonar_client.get_analyses(components)


@ocean.router.post("/webhook")
async def handle_sonarqube_webhook(data: dict[str, Any]) -> None:
    logger.info(
        f"Processing Sonarqube webhook for event type: {data.get('project', {}).get('key')}"
    )

    project = data.get("project", {})
    issues = await sonar_client.get_issues([project])
    analysis = await sonar_client.get_analyses([project])

    await ocean.register_raw(ObjectKind.ISSUES, issues)
    await ocean.register_raw(ObjectKind.ANALYSIS, analysis)


@ocean.on_start()
async def on_start() -> None:
    await sonar_client.get_or_create_webhook_url()
