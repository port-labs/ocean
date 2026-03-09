from loguru import logger
from clients.github_client import GitHubClient
from strategies import (
    LegacyOrganizationMetricsStrategy,
    OrganizationUsageMetricsStrategy,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


async def fetch_organization_metrics(
    github_client: GitHubClient,
    strategy: OrganizationUsageMetricsStrategy | LegacyOrganizationMetricsStrategy,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for organizations_batch in github_client.get_organizations():
        for organization in organizations_batch:
            organization_metrics = await strategy.fetch_metrics(
                github_client, organization
            )

            if not organization_metrics:
                continue

            strategy._enrich_metrics_with_organization(
                organization_metrics, organization
            )

            for metrics in organization_metrics:
                record_date = strategy._get_record_date_key(metrics)
                logger.info(
                    f"Received metrics of day {record_date} for organization {organization['login']}"
                )
            yield organization_metrics
