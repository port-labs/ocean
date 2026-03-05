from enum import StrEnum
from typing import cast

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from integration import CopilotOrganizationMetricsResourceConfig
from clients.client_factory import create_github_client
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


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
    use_new_api = getattr(selector, "use_usage_metrics", False)

    async for organizations_batch in github_client.get_organizations():
        for organization in organizations_batch:

            organization_metrics = None

            if use_new_api:
                logger.info(
                    (
                        f"Feature Flag enabled: Fetching NEW 28-day usage metrics for organization {organization['login']}."
                        " This API is in preview and may be subject to change."
                    )
                )
                organization_metrics = (
                    await github_client.get_new_usage_metrics_for_organization(
                        organization
                    )
                )
            else:
                logger.warning(
                    f'Feature Flag disabled: Fetching OLD 7-day metrics for organization {organization["login"]}.'
                )
                try:
                    organization_metrics = (
                        await github_client.get_legacy_metrics_for_organization(
                            organization
                        )
                    )

                except Exception as e:
                    logger.warning(
                        f"Error fetching legacy metrics for organization {organization['login']}: {e}"
                    )

                    organization_metrics = None

                if not organization_metrics:
                    logger.warning(
                        f"Legacy metrics API yielded no metrics for organization {organization['login']}. Falling back to new 28-usage metrics API."
                    )
                    organization_metrics = (
                        await github_client.get_new_usage_metrics_for_organization(
                            organization
                        )
                    )

            if not organization_metrics:
                logger.warning(
                    f"No metrics found for organization {organization['login']} using either API."
                )
                continue

            for metrics in organization_metrics:
                logger.info(
                    f"Received metrics of day {metrics['date']} for organization {organization['login']}"
                )
                metrics["__organization"] = organization
            yield organization_metrics


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting github-copilot integration")
