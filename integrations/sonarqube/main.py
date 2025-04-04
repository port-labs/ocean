from typing import cast
from loguru import logger
from utils import produce_component_params
from initialize_client import init_sonar_client
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from integration import (
    ObjectKind,
    SonarQubeGAProjectResourceConfig,
    SonarQubeIssueResourceConfig,
    SonarQubeProjectResourceConfig,
)
from webhook_processors.project_webhook_processor import ProjectWebhookProcessor
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.analysis_webhook_processor import AnalysisWebhookProcessor


@ocean.on_resync(ObjectKind.PROJECTS)
async def on_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sonar_client = init_sonar_client()
    logger.warning(
        "The `project` resource is deprecated. Please use `projects_ga` instead."
    )
    selector = cast(SonarQubeProjectResourceConfig, event.resource_config).selector
    sonar_client.metrics = selector.metrics

    component_params = produce_component_params(sonar_client, selector)

    fetched_projects = False
    async for projects in sonar_client.get_components(query_params=component_params):
        logger.info(f"Received project batch of size: {len(projects)}")
        yield projects
        fetched_projects = True

    if not fetched_projects:
        logger.error("No projects found in Sonarqube")
        raise RuntimeError(
            "No projects found in Sonarqube, failing the resync to avoid data loss"
        )


@ocean.on_resync(ObjectKind.PROJECTS_GA)
async def on_ga_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sonar_client = init_sonar_client()
    selector = cast(SonarQubeGAProjectResourceConfig, event.resource_config).selector
    sonar_client.metrics = selector.metrics
    params = {}
    if api_filters := selector.api_filters:
        params = api_filters.generate_request_params()

    async for projects in sonar_client.get_custom_projects(params, enrich_project=True):
        logger.info(f"Received project batch of size: {len(projects)}")
        yield projects


@ocean.on_resync(ObjectKind.ISSUES)
async def on_issues_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sonar_client = init_sonar_client()
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
    sonar_client = init_sonar_client()
    if not ocean.integration_config["sonar_is_on_premise"]:
        logger.info("Sonar is not on-premise, processing SonarCloud on saas analysis")
        async for analyses_list in sonar_client.get_all_sonarcloud_analyses():
            logger.info(f"Received analysis batch of size: {len(analyses_list)}")
            yield analyses_list


@ocean.on_resync(ObjectKind.ONPREM_ANALYSIS)
async def on_onprem_analysis_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sonar_client = init_sonar_client()
    if ocean.integration_config["sonar_is_on_premise"]:
        logger.info("Sonar is on-premise, processing on-premise SonarQube analysis")
        async for analyses_list in sonar_client.get_all_sonarqube_analyses():
            logger.info(f"Received analysis batch of size: {len(analyses_list)}")
            yield analyses_list


@ocean.on_resync(ObjectKind.PORTFOLIOS)
async def on_portfolio_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sonar_client = init_sonar_client()
    async for portfolio_list in sonar_client.get_all_portfolios():
        logger.info(f"Received portfolio batch of size: {len(portfolio_list)}")
        yield portfolio_list


@ocean.on_start()
async def on_start() -> None:
    if not ocean.integration_config.get("sonar_organization_id"):
        if not ocean.integration_config["sonar_is_on_premise"]:
            raise ValueError(
                "Organization ID is required for SonarCloud. Please specify a valid sonarOrganizationId"
            )

    sonar_client = init_sonar_client()
    sonar_client.sanity_check()

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    # We are making the real-time subscription of Sonar webhook events optional. That said,
    # we only subscribe to webhook events when the user supplies the app_host config variable
    if ocean.app.base_url:
        await sonar_client.get_or_create_webhook_url()


ocean.add_webhook_processor("/webhook", ProjectWebhookProcessor)
ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", AnalysisWebhookProcessor)
