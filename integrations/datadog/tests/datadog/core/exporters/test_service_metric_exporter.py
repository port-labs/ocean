from unittest.mock import AsyncMock, patch

import httpx
import pytest

from datadog.client import DatadogClient
from datadog.core.exporters.service_metric_exporter import (
    DEFAULT_SLEEP_TIME,
    ServiceMetricExporter,
)


@pytest.mark.asyncio
async def test_fetch_with_rate_limit_handling_retries_after_quota_wait(
    mock_datadog_client: DatadogClient,
) -> None:
    low_quota_response = httpx.Response(
        200,
        json={"series": []},
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1"},
        request=httpx.Request("GET", "https://api.datadoghq.com/api/v1/query"),
    )
    success_response = httpx.Response(
        200,
        json={"series": [{"pointlist": []}]},
        headers={"X-RateLimit-Remaining": "100"},
        request=httpx.Request("GET", "https://api.datadoghq.com/api/v1/query"),
    )

    exporter = ServiceMetricExporter(mock_datadog_client)

    with (
        patch.object(
            mock_datadog_client.http_client,
            "request",
            new_callable=AsyncMock,
            side_effect=[low_quota_response, success_response],
        ) as mock_request,
        patch(
            "datadog.core.exporters.service_metric_exporter.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        result = await exporter._send_rate_limited_request(
            "https://api.datadoghq.com/api/v1/query"
        )

    assert result == {"series": [{"pointlist": []}]}
    assert mock_request.await_count == 2
    mock_sleep.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_fetch_with_rate_limit_handling_uses_default_sleep_when_reset_header_missing(
    mock_datadog_client: DatadogClient,
) -> None:
    low_quota_response = httpx.Response(
        200,
        json={"series": []},
        headers={"X-RateLimit-Remaining": "0"},
        request=httpx.Request("GET", "https://api.datadoghq.com/api/v1/query"),
    )
    success_response = httpx.Response(
        200,
        json={"series": [{"pointlist": []}]},
        headers={"X-RateLimit-Remaining": "100"},
        request=httpx.Request("GET", "https://api.datadoghq.com/api/v1/query"),
    )

    exporter = ServiceMetricExporter(mock_datadog_client)

    with (
        patch.object(
            mock_datadog_client.http_client,
            "request",
            new_callable=AsyncMock,
            side_effect=[low_quota_response, success_response],
        ),
        patch(
            "datadog.core.exporters.service_metric_exporter.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        await exporter._send_rate_limited_request(
            "https://api.datadoghq.com/api/v1/query"
        )

    mock_sleep.assert_awaited_once_with(DEFAULT_SLEEP_TIME)
