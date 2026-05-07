from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from clients.pagerduty import PagerDutyClient
from clients.rate_limiter import PagerDutyDailyRateLimitExceededError
from utils import enrich_service_with_analytics_data


def _service(service_id: str) -> dict[str, Any]:
    return {"id": service_id, "name": f"svc-{service_id}"}


class TestEnrichServiceWithAnalyticsData:
    @pytest.mark.asyncio
    async def test_returns_services_enriched_with_matched_analytics(self) -> None:
        services = [_service("S1"), _service("S2")]
        analytics = [
            {"service_id": "S1", "mean_seconds_to_resolve": 100},
            {"service_id": "S2", "mean_seconds_to_resolve": 200},
        ]
        client = MagicMock(spec=PagerDutyClient)
        client.get_service_analytics = AsyncMock(return_value=analytics)

        result = await enrich_service_with_analytics_data(client, services, 3)

        assert result == [
            {**services[0], "__analytics": analytics[0]},
            {**services[1], "__analytics": analytics[1]},
        ]
        client.get_service_analytics.assert_awaited_once_with(["S1", "S2"], 3)

    @pytest.mark.asyncio
    async def test_unmatched_service_gets_none(self) -> None:
        services = [_service("S1"), _service("S2")]
        client = MagicMock(spec=PagerDutyClient)
        client.get_service_analytics = AsyncMock(
            return_value=[{"service_id": "S1", "mean_seconds_to_resolve": 100}]
        )

        result = await enrich_service_with_analytics_data(client, services, 3)

        assert result[0]["__analytics"] == {
            "service_id": "S1",
            "mean_seconds_to_resolve": 100,
        }
        assert result[1]["__analytics"] is None

    @pytest.mark.asyncio
    async def test_daily_rate_limit_returns_unenriched_without_raising(self) -> None:
        services = [_service("S1"), _service("S2")]
        client = MagicMock(spec=PagerDutyClient)
        client.get_service_analytics = AsyncMock(
            side_effect=PagerDutyDailyRateLimitExceededError(
                "PagerDuty analytics daily quota exhausted; resets in 49000s."
            )
        )

        result = await enrich_service_with_analytics_data(client, services, 3)

        assert result == [
            {**services[0], "__analytics": None},
            {**services[1], "__analytics": None},
        ]

    @pytest.mark.asyncio
    async def test_generic_exception_returns_unenriched_without_raising(self) -> None:
        services = [_service("S1")]
        client = MagicMock(spec=PagerDutyClient)
        client.get_service_analytics = AsyncMock(side_effect=RuntimeError("boom"))

        result = await enrich_service_with_analytics_data(client, services, 3)

        assert result == [{**services[0], "__analytics": None}]

    @pytest.mark.asyncio
    async def test_empty_services_yields_empty(self) -> None:
        client = MagicMock(spec=PagerDutyClient)
        client.get_service_analytics = AsyncMock(return_value=[])

        result = await enrich_service_with_analytics_data(client, [], 3)

        assert result == []
        client.get_service_analytics.assert_awaited_once_with([], 3)
