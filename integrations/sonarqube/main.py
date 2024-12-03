from typing import Any, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import SonarQubeClient
from integration import (
    CustomSelector,
    ObjectKind,
    SonarQubeGAProjectResourceConfig,
    SonarQubeIssueResourceConfig,
    SonarQubeProjectResourceConfig,
)


def init_sonar_client() -> SonarQubeClient:
    return SonarQubeClient(
        ocean.integration_config.get("sonar_url", "https://sonarcloud.io"),
        ocean.integration_config["sonar_api_token"],
        ocean.integration_config.get("sonar_organization_id"),
        ocean.integration_config.get("app_host"),
        ocean.integration_config["sonar_is_on_premise"],
    )


def produce_component_params(
    client: SonarQubeClient, selector: Any, initial_params: dict[str, Any] = {}
) -> dict[str, Any]:
    component_query_params: dict[str, Any] = {}
    if client.organization_id:
        component_query_params["organization"] = client.organization_id

    ## Handle query_params based on environment
    if client.is_onpremise:
        if initial_params:
            component_query_params.update(initial_params)
        elif event.resource_config:
            # This might be called from places where event.resource_config is not set
            # like on_start() when creating webhooks

            selector = cast(CustomSelector, event.resource_config.selector)
            component_query_params.update(selector.generate_request_params())
    return component_query_params


sonar_client = init_sonar_client()


@ocean.on_resync(ObjectKind.PROJECTS)
async def on_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Sonarqube resource: {kind}")

    selector = cast(SonarQubeProjectResourceConfig, event.resource_config).selector
    sonar_client.metrics = selector.metrics

    component_params = produce_component_params(sonar_client, selector)

    async for projects in sonar_client.get_components(query_params=component_params):
        logger.info(f"Received project batch of size: {len(projects)}")
        yield projects


@ocean.on_resync(ObjectKind.GA_PROJECTS)
async def on_ga_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Sonarqube resource: {kind}")

    selector = cast(SonarQubeGAProjectResourceConfig, event.resource_config).selector
    sonar_client.metrics = selector.metrics

    async for projects in sonar_client.get_projects(selector.generate_request_params()):
        logger.info(f"Received project batch of size: {len(projects)}")
        yield projects


@ocean.on_resync(ObjectKind.ISSUES)
async def on_issues_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(SonarQubeIssueResourceConfig, event.resource_config).selector
    query_params = selector.generate_request_params()
    project_query_params = (
        selector.project_api_filters
        and selector.project_api_filters.generate_request_params()
    ) or {}

    async for issues_list in sonar_client.get_all_issues(
        query_params=query_params,
        project_query_params=project_query_params,
    ):
        logger.info(f"Received issues batch of size: {len(issues_list)}")
        yield issues_list


@ocean.on_resync(ObjectKind.ANALYSIS)
@ocean.on_resync(ObjectKind.SASS_ANALYSIS)
async def on_saas_analysis_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if not ocean.integration_config["sonar_is_on_premise"]:
        logger.info("Sonar is not on-premise, processing SonarCloud on saas analysis")
        async for analyses_list in sonar_client.get_all_sonarcloud_analyses():
            logger.info(f"Received analysis batch of size: {len(analyses_list)}")
            yield analyses_list


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
    await ocean.register_raw(ObjectKind.PROJECTS, [project_data])
    async for issues_data in sonar_client.get_issues_by_component(project):
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
