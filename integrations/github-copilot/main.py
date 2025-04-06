from enum import StrEnum

from port_ocean.context.ocean import ocean
from clients.client_factory import create_github_client
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    COPILOT_TEAM_METRICS = "copilot-team-metrics"
    COPILOT_ORGANIZATION_METRICS = "copilot-organization-metrics"


@ocean.on_resync(ObjectKind.COPILOT_TEAM_METRICS)
async def on_resync_copilot_team_metrics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = create_github_client()
    async for organization in github_client.get_organizations():
        async for team in github_client.get_teams_of_organization(organization):
            async for metrics in github_client.get_metrics_for_team(organization, team):
                logger.info(
                    f"Received metrics of day {metrics['date']} for team {team['slug']} of organization {organization['login']}"
                )
                metrics["__organization"] = organization
                metrics["__team"] = team
                yield [metrics]


@ocean.on_resync(ObjectKind.COPILOT_ORGANIZATION_METRICS)
async def on_resync_copilot_organization_metrics(
    kind: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = create_github_client()
    async for organization in github_client.get_organizations():
        async for metrics in github_client.get_metrics_for_organization(organization):
            logger.info(
                f"Received metrics of day {metrics['date']} for organization {organization['login']}"
            )
            metrics["__organization"] = organization
            yield [metrics]


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting github-copilot integration")
