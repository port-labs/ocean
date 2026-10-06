from unittest.mock import AsyncMock, patch

import pytest

from datadog.client import DatadogClient
from datadog.core.exporters.monitor_exporter import GetMonitorOptions, MonitorExporter


@pytest.mark.asyncio
async def test_get_resource_without_restriction_policy_enrichment(
    mock_datadog_client: DatadogClient,
) -> None:
    monitor = {"id": "123", "name": "monitor"}
    exporter = MonitorExporter(mock_datadog_client)

    with (
        patch.object(
            mock_datadog_client,
            "send_api_request",
            new_callable=AsyncMock,
            return_value=monitor,
        ) as mock_request,
        patch.object(
            exporter.rp_exporter,
            "enrich_resource_with_restriction_policy",
            new_callable=AsyncMock,
        ) as mock_enrich,
    ):
        result = await exporter.get_resource(GetMonitorOptions(resource_id="123"))

    assert result == monitor
    mock_request.assert_awaited_once_with(
        f"{mock_datadog_client.api_url}/api/v1/monitor/123"
    )
    mock_enrich.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_resource_with_restriction_policy_enrichment(
    mock_datadog_client: DatadogClient,
) -> None:
    monitor = {"id": "123", "name": "monitor"}
    enriched_monitor = {
        "id": "123",
        "name": "monitor",
        "__restrictedUsers": [],
        "__restrictedTeams": [],
        "__restrictedRoles": [],
    }
    exporter = MonitorExporter(mock_datadog_client)

    with (
        patch.object(
            mock_datadog_client,
            "send_api_request",
            new_callable=AsyncMock,
            return_value=monitor,
        ),
        patch.object(
            exporter.rp_exporter,
            "enrich_resource_with_restriction_policy",
            new_callable=AsyncMock,
            return_value=enriched_monitor,
        ) as mock_enrich,
    ):
        result = await exporter.get_resource(
            GetMonitorOptions(resource_id="123", include_restriction_policy=True)
        )

    assert result == enriched_monitor
    mock_enrich.assert_awaited_once_with("monitor", monitor)
