from enum import StrEnum
from typing import cast, TYPE_CHECKING

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from integration import CopilotOrganizationMetricsResourceConfig
from clients.client_factory import create_github_client
from strategies import get_metrics_strategy
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

if TYPE_CHECKING:
    pass


class ObjectKind(StrEnum):
    COPILOT_TEAM_METRICS = "copilot-team-metrics"
    COPILOT_ORGANIZATION_METRICS = "copilot-organization-metrics"


@ocean.on_resync(ObjectKind.COPILOT_TEAM_METRICS)
async def on_resync_copilot_team_metrics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.warning(
        "DEPRECATION WARNING: GitHub is sunsetting Team Metrics on April 2, 2026. This resource will be removed in a future update."
    )
    github_client = create_github_client()
    async for organizations_batch in github_client.get_organizations():
        for organization in organizations_batch:
            async for teams_batch in github_client.get_teams_of_organization(
                organization
            ):
                for team in teams_batch:
                    team_metrics = await github_client.get_metrics_for_team(
                        organization, team
                    )
                    if not team_metrics:
                        continue

                    for metrics in team_metrics:
                        logger.info(
                            f"Received metrics of day {metrics['date']} for team {team['slug']} of organization {organization['login']}"
                        )
                        metrics["__organization"] = organization
                        metrics["__team"] = team
                    yield team_metrics


@ocean.on_resync(ObjectKind.COPILOT_ORGANIZATION_METRICS)
async def on_resync_copilot_organization_metrics(
    kind: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = create_github_client()

    selector = cast(
        CopilotOrganizationMetricsResourceConfig, event.resource_config
    ).selector
    use_new_api = selector.use_usage_metrics

    strategy = get_metrics_strategy(use_new_api)

    async for organizations_batch in github_client.get_organizations():
        for organization in organizations_batch:
            organization_metrics = await strategy.fetch_metrics(
                github_client, organization
            )
            strategy._enrich_metrics_with_organization(
                organization_metrics, organization
            )
            for metrics in organization_metrics:
                record_date = strategy._get_record_date_key(metrics)
                logger.info(
                    f"Received metrics of day {record_date} for organization {organization['login']}"
                )
            yield organization_metrics


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting github-copilot integration")
