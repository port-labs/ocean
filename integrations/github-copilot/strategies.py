from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from clients.github_client import GitHubClient


class OrganizationMetricsStrategy(ABC):
    @abstractmethod
    async def fetch_metrics(
        self, github_client: "GitHubClient", organization: dict[str, Any]
    ) -> list[dict[str, Any]]:
        pass

    def _enrich_metrics_with_organization(
        self, metrics: list[dict[str, Any]], organization: dict[str, Any]
    ) -> list[dict[str, Any]]:
        for metric in metrics:
            metric["__organization"] = organization
        return metrics


class LegacyMetricsStrategy(OrganizationMetricsStrategy):
    async def fetch_metrics(
        self, github_client: "GitHubClient", organization: dict[str, Any]
    ) -> list[dict[str, Any]]:
        try:
            logger.warning(
                f'Feature Flag disabled: Fetching metrics (using Legacy Metrics API) for organization {organization["login"]}.'
            )
            return await github_client.get_legacy_metrics_for_organization(organization)
        except Exception as e:
            logger.error(
                f"Error fetching legacy metrics for organization {organization['login']}: {e}"
            )
            raise e

    def _get_record_date_key(self, metrics: dict[str, Any]) -> str:
        return metrics["date"]


class NewUsageMetricsStrategy(OrganizationMetricsStrategy):
    async def fetch_metrics(self, github_client, organization) -> list[dict[str, Any]]:
        try:
            logger.info(
                (
                    f"Feature Flag enabled: Fetching NEW 28-day usage metrics for organization {organization['login']}."
                )
            )
            return await github_client.get_organization_usage_metrics(organization)
        except Exception as e:
            logger.error(
                f"Error fetching new usage metrics for organization {organization['login']}: {e}"
            )
            raise e

    def _get_record_date_key(self, metrics: dict[str, Any]) -> str:
        return metrics["day"]


def get_metrics_strategy(use_new_api: bool) -> OrganizationMetricsStrategy:
    if use_new_api:
        return NewUsageMetricsStrategy()
    return LegacyMetricsStrategy()
