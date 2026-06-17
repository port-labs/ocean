from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.exporters.claude_ai.user_activity_exporter import (
    ClaudeAIUserActivityExporter,
)
from core.exporters.claude_ai.user_usage_exporter import ClaudeAIUserUsageExporter
from core.exporters.platform.code_analytics_exporter import (
    ClaudePlatformCodeAnalyticsExporter,
)
from core.exporters.platform.usage_exporter import ClaudePlatformUsageExporter


def _page_generator(
    *pages: list[dict[str, Any]],
) -> AsyncGenerator[list[dict[str, Any]], None]:
    async def _generator() -> AsyncGenerator[list[dict[str, Any]], None]:
        for page in pages:
            yield page

    return _generator()


# ---------------------------------------------------------------------------
# Platform exporters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_platform_usage_exporter_uses_messages_endpoint() -> None:
    client = MagicMock()
    client.send_paginated_request.return_value = _page_generator([{"id": "u1"}])
    exporter = ClaudePlatformUsageExporter(client)

    results = [
        page
        async for page in exporter.get_paginated_resources(
            {
                "starting_at": "2026-01-01T00:00:00Z",
                "limit": 30,
                "bucket_width": "1d",
                "group_by": ["workspace_id"],
            }
        )
    ]

    assert results == [[{"id": "u1"}]]
    client.send_paginated_request.assert_called_once_with(
        "/v1/organizations/usage_report/messages",
        {
            "starting_at": "2026-01-01T00:00:00Z",
            "limit": 30,
            "bucket_width": "1d",
            "group_by[]": ["workspace_id"],
        },
    )


@pytest.mark.asyncio
async def test_platform_code_analytics_exporter_soft_fails_on_403() -> None:
    client = MagicMock()
    client.send_paginated_request.return_value = _page_generator([{"id": "a1"}])
    exporter = ClaudePlatformCodeAnalyticsExporter(client)

    results = [
        page
        async for page in exporter.get_paginated_resources(
            {"starting_at": "2026-01-01", "limit": 30}
        )
    ]

    assert results == [[{"id": "a1"}]]
    client.send_paginated_request.assert_called_once_with(
        "/v1/organizations/usage_report/claude_code",
        {"starting_at": "2026-01-01", "limit": 30},
        soft_fail_statuses={403},
    )


# ---------------------------------------------------------------------------
# Claude AI (Enterprise) exporters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_activity_exporter_injects_date() -> None:
    client = MagicMock()
    client.send_paginated_request.return_value = _page_generator(
        [{"user": {"id": "user_1"}}]
    )
    exporter = ClaudeAIUserActivityExporter(client)

    results = [
        page
        async for page in exporter.get_paginated_resources(
            {"date": "2026-03-05", "limit": 30}
        )
    ]

    assert results == [[{"user": {"id": "user_1"}, "__date": "2026-03-05"}]]
    client.send_paginated_request.assert_called_once_with(
        "/v1/organizations/analytics/users",
        {"date": "2026-03-05", "limit": 30},
        soft_fail_statuses={403},
    )


@pytest.mark.asyncio
async def test_user_usage_exporter_builds_array_params_and_stamps_range() -> None:
    client = MagicMock()
    client.send_paginated_request.return_value = _page_generator(
        [{"actor": {"user_id": "user_1"}}]
    )
    exporter = ClaudeAIUserUsageExporter(client)

    results = [
        page
        async for page in exporter.get_paginated_resources(
            {
                "starting_at": "2026-03-01T00:00:00Z",
                "ending_at": "2026-03-15T00:00:00Z",
                "limit": 30,
                "exclude_deleted_users": True,
                "products": ["chat", "claude_code"],
                "group_by": ["model"],
            }
        )
    ]

    assert results == [
        [
            {
                "actor": {"user_id": "user_1"},
                "__starting_at": "2026-03-01T00:00:00Z",
                "__ending_at": "2026-03-15T00:00:00Z",
            }
        ]
    ]
    client.send_paginated_request.assert_called_once_with(
        "/v1/organizations/analytics/user_usage_report",
        {
            "starting_at": "2026-03-01T00:00:00Z",
            "ending_at": "2026-03-15T00:00:00Z",
            "limit": 30,
            "exclude_deleted_users": True,
            "products[]": ["chat", "claude_code"],
            "group_by[]": ["model"],
        },
        soft_fail_statuses={403},
    )
