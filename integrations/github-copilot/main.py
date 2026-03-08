from enum import StrEnum
from typing import Any, cast, TYPE_CHECKING

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from integration import CopilotOrganizationMetricsResourceConfig
from clients.client_factory import create_github_client
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


if TYPE_CHECKING:
    from clients.github_client import GitHubClient



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


from abc import ABC, abstractmethod

class OrganizationMetricsStrategy(ABC):
    @abstractmethod
    async def fetch_metrics(self, github_client: "GitHubClient", organization: dict[str, Any]) -> list[dict[str, Any]]:
        pass


    def _enrich_metrics_with_organization(self, metrics: list[dict[str, Any]], organization: dict[str, Any]) -> list[dict[str, Any]]:
        for metric in metrics:
            metric["__organization"] = organization
        return metrics



class LegacyMetricsStrategy(OrganizationMetricsStrategy):
    async def fetch_metrics(self, github_client: "GitHubClient", organization: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            logger.warning(
                f'Feature Flag disabled: Fetching metrics (using Legacy Metrics API) for organization {organization["login"]}.'
            )
            return await github_client.get_legacy_metrics_for_organization(
                organization
            )
        except Exception as e:
            logger.error(
                f"Error fetching legacy metrics for organization {organization['login']}: {e}"
            )
            raise e

    def _get_record_date_key(self, metrics: list[dict[str, Any]]) -> str:
        return metrics['date']

class NewUsageMetricsStrategy(OrganizationMetricsStrategy):
    async def fetch_metrics(self, github_client, organization) -> list[dict[str, Any]]:
        try:
            logger.info(
                (
                    f"Feature Flag enabled: Fetching NEW 28-day usage metrics for organization {organization['login']}."
                    " This API is in preview and may be subject to change."
                )
            )
            return await github_client.get_new_usage_metrics_for_organization(
                organization
            )
        except Exception as e:
            logger.error(
                f"Error fetching new usage metrics for organization {organization['login']}: {e}"
            )
            raise e

    def _get_record_date_key(self, metrics: list[dict[str, Any]]) -> str:
        return metrics['day']


def get_metrics_strategy(use_new_api: bool) -> OrganizationMetricsStrategy:
    if use_new_api:
        return NewUsageMetricsStrategy()
    else:
        return LegacyMetricsStrategy()

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
            organization_metrics = await strategy.fetch_metrics(github_client, organization)

            for metrics in organization_metrics:
                record_date = strategy._get_record_date_key(metrics)
                logger.info(
                    f"Received metrics of day {record_date} for organization {organization['login']}"
                )
                strategy._enrich_metrics_with_organization(metrics, organization)
            yield organization_metrics


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting github-copilot integration")
