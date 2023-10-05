from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import SonarQubeClient


class ObjectKind:
    PROJECTS = "projects"
    ISSUES = "issues"
    ANALYSIS = "analysis"


def init_sonar_client() -> SonarQubeClient:
    return SonarQubeClient(
        ocean.integration_config.get("sonar_url", "https://sonarcloud.io"),
        ocean.integration_config["sonar_api_token"],
        ocean.integration_config.get("sonar_organization_id", ""),
        ocean.integration_config.get("app_host", ""),
    )


def is_onpremise_deployment() -> bool:
    return ocean.integration_config.get("sonar_url") != "https://sonarcloud.io"

def organization_key_missing_for_onpremise() -> bool:
    return (not ocean.integration_config.get("sonar_organization_id") and is_onpremise_deployment())

@ocean.on_resync(ObjectKind.PROJECTS)
async def on_project_resync(kind: str) -> list[dict[str, Any]]:
    logger.info(f"Listing Sonarqube resource: {kind}")
    sonar_client = init_sonar_client()
    return await sonar_client.get_all_projects()


@ocean.on_resync(ObjectKind.ISSUES)
async def on_issues_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Sonarqube resource: {kind}")
    sonar_client = init_sonar_client()
    async for issues_list in sonar_client.get_all_issues():
        for issue in issues_list:
            yield [issue]


@ocean.on_resync(ObjectKind.ANALYSIS)
async def on_analysis_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Sonarqube resource: {kind}")
    if is_onpremise_deployment():
        logger.debug(
            "Skipping resync because the integration does not support on-premise Sonarqube deployment"
        )
        return

    sonar_client = init_sonar_client()

    async for analyses_list in sonar_client.get_all_analyses():
        for analysis_data in analyses_list:
            yield [analysis_data]


@ocean.router.post("/webhook")
async def handle_sonarqube_webhook(webhook_data: dict[str, Any]) -> None:
    logger.info(
        f"Processing Sonarqube webhook for event type: {webhook_data.get('project', {}).get('key')}"
    )
    sonar_client = init_sonar_client()

    project = await sonar_client.get_single_component(
        webhook_data.get("project", {})
    )  ## making sure we're getting the right project details
    project_data = await sonar_client.get_single_project(project)
    issues_data = await sonar_client.get_issues_by_component(project)
    await ocean.register_raw(ObjectKind.PROJECTS, [project_data])
    await ocean.register_raw(ObjectKind.ISSUES, issues_data)

    if is_onpremise_deployment():
        logger.debug(
            "Skipping real-time update of analysis because the integration does not support on-premise Sonarqube deployment"
        )
        return

    analysis_data = await sonar_client.get_analysis_for_task(webhook_data=webhook_data)
    await ocean.register_raw(ObjectKind.ANALYSIS, [analysis_data])

    logger.info("Webhook event processed")


@ocean.on_start()
async def on_start() -> None:
    if organization_key_missing_for_onpremise():
        logger.warning("Organization key is missing for an on-premise Sonarqube setup")
    ## We are making the real-time subscription of Sonar webhook events optional. That said, we only subscribe to webhook events when the user supplies the app_host config variable
    if ocean.integration_config.get("app_host"):
        sonar_client = init_sonar_client()
        await sonar_client.get_or_create_webhook_url()
