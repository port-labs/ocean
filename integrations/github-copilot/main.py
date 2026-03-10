from enum import StrEnum

from port_ocean.context.ocean import ocean
from clients.client_factory import create_github_client
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    COPILOT_TEAM_METRICS = "copilot-team-metrics"
    COPILOT_ORGANIZATION_METRICS = "copilot-organization-metrics"
    ORGANIZATION_USAGE_METRICS = "organization-usage-metrics"


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
    logger.warning(
        "DEPRECATION WARNING: GitHub is sunsetting the legacy Copilot Metrics API on April 2, 2026. "
        "Please migrate to the 'organization-usage-metrics' kind to use the new 28-day API."
    )
    async for organizations_batch in github_client.get_organizations():
        for organization in organizations_batch:
            organization_metrics = (
                await github_client.get_legacy_metrics_for_organization(organization)
            )
            if not organization_metrics:
                continue

            github_client._enrich_metrics_with_organization(
                organization_metrics, organization
            )
            logger.info(
                f"Received len(organization_metrics) metrics for organization {organization['login']}"
            )
            yield organization_metrics


@ocean.on_resync(ObjectKind.ORGANIZATION_USAGE_METRICS)
async def on_resync_organization_usage_metrics(
    kind: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = create_github_client()
    async for batch in github_client.fetch_organization_usage_metrics():
        yield batch


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting github-copilot integration")
