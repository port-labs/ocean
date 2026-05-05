from typing import Any

from loguru import logger

from clients.pagerduty import PagerDutyClient
from clients.rate_limiter import PagerDutyDailyRateLimitExceededError


def _services_without_analytics(
    services: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [{**service, "__analytics": None} for service in services]


async def enrich_service_with_analytics_data(
    client: PagerDutyClient, services: list[dict[str, Any]], months_period: int
) -> list[dict[str, Any]]:
    service_ids = [service["id"] for service in services]
    try:
        services_analytics = await client.get_service_analytics(
            service_ids, months_period
        )
        analytics_by_service = {
            analytics["service_id"]: analytics for analytics in services_analytics
        }
        return [
            {**service, "__analytics": analytics_by_service.get(service["id"])}
            for service in services
        ]
    except PagerDutyDailyRateLimitExceededError as e:
        logger.warning(
            f"Skipping service analytics enrichment for {len(service_ids)} services: {e}"
        )
        return _services_without_analytics(services)
    except Exception as e:
        logger.error(f"Failed to fetch analytics for service {service_ids}: {e}")
        return _services_without_analytics(services)
