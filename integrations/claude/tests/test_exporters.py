from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from core.exporters.activity_summary_exporter import ClaudeActivitySummaryExporter
from core.exporters.cost_exporter import ClaudeCostExporter
from core.exporters.usage_exporter import ClaudeUsageExporter
from core.exporters.user_activity_exporter import ClaudeUserActivityExporter
from core.exporters.user_cost_report_exporter import ClaudeUserCostReportExporter
from core.exporters.user_usage_report_exporter import ClaudeUserUsageReportExporter


def _page_generator(
    *pages: list[dict[str, object]],
) -> AsyncGenerator[list[dict[str, object]], None]:
    async def _generator() -> AsyncGenerator[list[dict[str, object]], None]:
        for page in pages:
            yield page

    return _generator()


@pytest.mark.asyncio
async def test_usage_exporter_calls_client_with_expected_params() -> None:
    client = MagicMock()
    client.get_usage_report_messages.return_value = _page_generator([{"id": "u1"}])
    exporter = ClaudeUsageExporter(client)

    results = [
        page
        async for page in exporter.get_paginated_resources(
            {
                "starting_at": "2026-01-01T00:00:00Z",
                "limit": 30,
                "bucket_width": "1d",
                "group_by": ["product"],
            }
        )
    ]

    assert results == [[{"id": "u1"}]]
    client.get_usage_report_messages.assert_called_once_with(
        {
            "starting_at": "2026-01-01T00:00:00Z",
            "limit": 30,
            "bucket_width": "1d",
            "group_by[]": ["product"],
        }
    )


@pytest.mark.asyncio
async def test_cost_exporter_calls_client_with_expected_params() -> None:
    client = MagicMock()
    client.get_cost_report.return_value = _page_generator([{"id": "c1"}])
    exporter = ClaudeCostExporter(client)

    results = [
        page
        async for page in exporter.get_paginated_resources(
            {
                "starting_at": "2026-01-01T00:00:00Z",
                "limit": 30,
                "bucket_width": "1d",
            }
        )
    ]

    assert results == [[{"id": "c1"}]]
    client.get_cost_report.assert_called_once_with(
        {
            "starting_at": "2026-01-01T00:00:00Z",
            "limit": 30,
            "bucket_width": "1d",
        }
    )


@pytest.mark.asyncio
async def test_cost_exporter_passes_group_by() -> None:
    client = MagicMock()
    client.get_cost_report.return_value = _page_generator([{"id": "c1"}])
    exporter = ClaudeCostExporter(client)

    await exporter.get_paginated_resources(
        {
            "starting_at": "2026-01-01T00:00:00Z",
            "limit": 30,
            "bucket_width": "1d",
            "group_by": ["cost_type"],
        }
    ).__anext__()

    client.get_cost_report.assert_called_once_with(
        {
            "starting_at": "2026-01-01T00:00:00Z",
            "limit": 30,
            "bucket_width": "1d",
            "group_by[]": ["cost_type"],
        }
    )


@pytest.mark.asyncio
async def test_user_activity_exporter_calls_client_with_expected_params() -> None:
    client = MagicMock()
    client.get_user_activity.return_value = _page_generator([{"id": "a1"}])
    exporter = ClaudeUserActivityExporter(client)

    results = [
        page
        async for page in exporter.get_paginated_resources(
            {
                "date": "2026-01-01",
                "limit": 30,
            }
        )
    ]

    assert results == [[{"id": "a1"}]]
    client.get_user_activity.assert_called_once_with(
        {
            "date": "2026-01-01",
            "limit": 30,
        }
    )


@pytest.mark.asyncio
async def test_activity_summary_exporter_yields_records() -> None:
    client = MagicMock()
    client.get_activity_summary = AsyncMock(
        return_value=[{"dau": 10, "wau": 50, "mau": 200}]
    )
    exporter = ClaudeActivitySummaryExporter(client)

    results = [
        page
        async for page in exporter.get_paginated_resources(
            {"starting_date": "2026-01-01"}
        )
    ]

    assert results == [[{"dau": 10, "wau": 50, "mau": 200}]]
    client.get_activity_summary.assert_called_once_with({"starting_date": "2026-01-01"})


@pytest.mark.asyncio
async def test_activity_summary_exporter_yields_nothing_when_empty() -> None:
    client = MagicMock()
    client.get_activity_summary = AsyncMock(return_value=[])
    exporter = ClaudeActivitySummaryExporter(client)

    results = [
        page
        async for page in exporter.get_paginated_resources(
            {"starting_date": "2026-01-01"}
        )
    ]

    assert results == []


@pytest.mark.asyncio
async def test_user_usage_report_exporter_calls_client_with_expected_params() -> None:
    client = MagicMock()
    client.get_user_usage_report.return_value = _page_generator([{"id": "uur1"}])
    exporter = ClaudeUserUsageReportExporter(client)

    results = [
        page
        async for page in exporter.get_paginated_resources(
            {
                "starting_at": "2026-01-01T00:00:00Z",
                "limit": 30,
                "order_by": "total_tokens",
            }
        )
    ]

    assert results == [[{"id": "uur1"}]]
    client.get_user_usage_report.assert_called_once_with(
        {
            "starting_at": "2026-01-01T00:00:00Z",
            "limit": 30,
            "order_by": "total_tokens",
        }
    )


@pytest.mark.asyncio
async def test_user_cost_report_exporter_calls_client_with_expected_params() -> None:
    client = MagicMock()
    client.get_user_cost_report.return_value = _page_generator([{"id": "ucr1"}])
    exporter = ClaudeUserCostReportExporter(client)

    results = [
        page
        async for page in exporter.get_paginated_resources(
            {
                "starting_at": "2026-01-01T00:00:00Z",
                "limit": 30,
                "order_by": "amount",
            }
        )
    ]

    assert results == [[{"id": "ucr1"}]]
    client.get_user_cost_report.assert_called_once_with(
        {
            "starting_at": "2026-01-01T00:00:00Z",
            "limit": 30,
            "order_by": "amount",
        }
    )
