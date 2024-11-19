from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import SonarQubeClient
from integration import ObjectKind


def init_sonar_client() -> SonarQubeClient:
    return SonarQubeClient(
        ocean.integration_config.get("sonar_url", "https://sonarcloud.io"),
        ocean.integration_config["sonar_api_token"],
        ocean.integration_config.get("sonar_organization_id"),
        ocean.integration_config.get("app_host"),
        ocean.integration_config["sonar_is_on_premise"],
    )


sonar_client = init_sonar_client()


@ocean.on_resync(ObjectKind.PROJECTS)
async def on_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Sonarqube resource: {kind}")

    fetched_projects = False

    async for project_list in sonar_client.get_all_projects():
        logger.info(f"Received project batch of size: {len(project_list)}")
        yield project_list
        fetched_projects = True

    if not fetched_projects:
        logger.error("No projects found in Sonarqube")
        raise RuntimeError(
            "No projects found in Sonarqube, failing the resync to avoid data loss"
        )


@ocean.on_resync(ObjectKind.ISSUES)
async def on_issues_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    fetched_issues = False
    async for issues_list in sonar_client.get_all_issues():
        logger.info(f"Received issues batch of size: {len(issues_list)}")
        yield issues_list
        fetched_issues = True

    if not fetched_issues:
        logger.error("No issues found in Sonarqube")
        raise RuntimeError(
            "No issues found in Sonarqube, failing the resync to avoid data loss"
        )


@ocean.on_resync(ObjectKind.ANALYSIS)
@ocean.on_resync(ObjectKind.SASS_ANALYSIS)
async def on_saas_analysis_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    fetched_analyses = False
    if not ocean.integration_config["sonar_is_on_premise"]:
        logger.info("Sonar is not on-premise, processing SonarCloud on saas analysis")
        async for analyses_list in sonar_client.get_all_sonarcloud_analyses():
            logger.info(f"Received analysis batch of size: {len(analyses_list)}")
            yield analyses_list
            fetched_analyses = True

        if not fetched_analyses:
            logger.error("No analysis found in Sonarqube")
            raise RuntimeError(
                "No analysis found in Sonarqube, failing the resync to avoid data loss"
            )


@ocean.on_resync(ObjectKind.ONPREM_ANALYSIS)
async def on_onprem_analysis_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if ocean.integration_config["sonar_is_on_premise"]:
        logger.info("Sonar is on-premise, processing on-premise SonarQube analysis")
        async for analyses_list in sonar_client.get_all_sonarqube_analyses():
            logger.info(f"Received analysis batch of size: {len(analyses_list)}")
            yield analyses_list


@ocean.on_resync(ObjectKind.PORTFOLIOS)
async def on_portfolio_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for portfolio_list in sonar_client.get_all_portfolios():
        logger.info(f"Received portfolio batch of size: {len(portfolio_list)}")
        yield portfolio_list


@ocean.router.post("/webhook")
async def handle_sonarqube_webhook(webhook_data: dict[str, Any]) -> None:
    logger.info(
        f"Processing Sonarqube webhook for event type: {webhook_data.get('project', {}).get('key')}"
    )

    project = await sonar_client.get_single_component(
        webhook_data.get("project", {})
    )  ## making sure we're getting the right project details
    project_data = await sonar_client.get_single_project(project)
    issues_data = await sonar_client.get_issues_by_component(project)
    await ocean.register_raw(ObjectKind.PROJECTS, [project_data])
    await ocean.register_raw(ObjectKind.ISSUES, issues_data)

    if ocean.integration_config["sonar_is_on_premise"]:
        onprem_analysis_data = await sonar_client.get_measures_for_all_pull_requests(
            project_key=project["key"]
        )
        await ocean.register_raw(ObjectKind.ONPREM_ANALYSIS, onprem_analysis_data)
    else:
        cloud_analysis_data = await sonar_client.get_analysis_for_task(
            webhook_data=webhook_data
        )
        await ocean.register_raw(ObjectKind.SASS_ANALYSIS, [cloud_analysis_data])
        await ocean.register_raw(ObjectKind.ANALYSIS, [cloud_analysis_data])

    logger.info("Webhook event processed")


@ocean.on_start()
async def on_start() -> None:
    if not ocean.integration_config.get("sonar_organization_id"):
        if not ocean.integration_config["sonar_is_on_premise"]:
            raise ValueError(
                "Organization ID is required for SonarCloud. Please specify a valid sonarOrganizationId"
            )

    sonar_client.sanity_check()

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    # We are making the real-time subscription of Sonar webhook events optional. That said,
    # we only subscribe to webhook events when the user supplies the app_host config variable
    if ocean.integration_config.get("app_host"):
        await sonar_client.get_or_create_webhook_url()
