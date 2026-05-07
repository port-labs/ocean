from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest

from core.exporters.code_analytics_exporter import ClaudeCodeAnalyticsExporter
from core.exporters.cost_exporter import ClaudeCostExporter
from core.exporters.usage_exporter import ClaudeUsageExporter


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
                "starting_at": "2025-01-01T00:00:00Z",
                "limit": 30,
                "bucket_width": "1d",
                "group_by": ["workspace_id"],
            }
        )
    ]

    assert results == [[{"id": "u1"}]]
    client.get_usage_report_messages.assert_called_once_with(
        {
            "starting_at": "2025-01-01T00:00:00Z",
            "limit": 30,
            "bucket_width": "1d",
            "group_by[]": ["workspace_id"],
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
                "starting_at": "2025-01-01T00:00:00Z",
                "limit": 30,
                "bucket_width": "1d",
            }
        )
    ]

    assert results == [[{"id": "c1"}]]
    client.get_cost_report.assert_called_once_with(
        {
            "starting_at": "2025-01-01T00:00:00Z",
            "limit": 30,
            "bucket_width": "1d",
        }
    )


@pytest.mark.asyncio
async def test_code_analytics_exporter_calls_client_with_expected_params() -> None:
    client = MagicMock()
    client.get_claude_code_report.return_value = _page_generator([{"id": "a1"}])
    exporter = ClaudeCodeAnalyticsExporter(client)

    results = [
        page
        async for page in exporter.get_paginated_resources(
            {
                "starting_at": "2025-01-01",
                "limit": 30,
            }
        )
    ]

    assert results == [[{"id": "a1"}]]
    client.get_claude_code_report.assert_called_once_with(
        {
            "starting_at": "2025-01-01",
            "limit": 30,
        }
    )
