from collections.abc import AsyncGenerator
from typing import Any

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.exporters.daily_usage_exporter import CursorDailyUsageExporter
from core.exporters.team_model_usage_exporter import CursorTeamModelUsageExporter
from core.exporters.usage_events_exporter import CursorUsageEventsExporter
from core.exporters.user_model_usage_exporter import CursorUserModelUsageExporter
from core.options import ListCursorAdminOptions, ListCursorAnalyticsOptions

ANALYTICS_OPTIONS: ListCursorAnalyticsOptions = {
    "startDate": "30d",
    "endDate": "0d",
}
ADMIN_OPTIONS: ListCursorAdminOptions = {
    "startDate": 1,
    "endDate": 2,
}


def _paginated(*payloads: dict[str, Any]) -> MagicMock:
    async def _gen(*_args: Any, **_kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        for payload in payloads:
            yield payload

    return _gen  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_team_model_usage_exporter_yields_data() -> None:
    client = MagicMock()
    client.send_api_request = AsyncMock(return_value={"data": [{"date": "2026-05-10"}]})
    exporter = CursorTeamModelUsageExporter(client)

    batches = [
        batch async for batch in exporter.get_paginated_resources(ANALYTICS_OPTIONS)
    ]

    assert batches == [[{"date": "2026-05-10"}]]
    client.send_api_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_model_usage_exporter_flattens_records() -> None:
    client = MagicMock()
    client.send_paginated_request = _paginated(
        {
            "data": {
                "a@port.io": [
                    {
                        "date": "2026-05-11",
                        "model_breakdown": {"default": {"messages": 3}},
                    }
                ],
                "b@port.io": [],
            }
        }
    )
    exporter = CursorUserModelUsageExporter(client)

    batches = [
        batch async for batch in exporter.get_paginated_resources(ANALYTICS_OPTIONS)
    ]

    assert batches == [
        [
            {
                "userEmail": "a@port.io",
                "date": "2026-05-11",
                "model_breakdown": {"default": {"messages": 3}},
            }
        ]
    ]


@pytest.mark.asyncio
async def test_daily_usage_exporter_yields_data() -> None:
    client = MagicMock()
    client.send_paginated_request = _paginated({"data": [{"userId": 1}]})
    exporter = CursorDailyUsageExporter(client)

    batches = [batch async for batch in exporter.get_paginated_resources(ADMIN_OPTIONS)]

    assert batches == [[{"userId": 1}]]


@pytest.mark.asyncio
async def test_usage_events_exporter_yields_usage_events() -> None:
    client = MagicMock()
    client.send_paginated_request = _paginated({"usageEvents": [{"model": "gpt"}]})
    exporter = CursorUsageEventsExporter(client)

    batches = [batch async for batch in exporter.get_paginated_resources(ADMIN_OPTIONS)]

    assert batches == [[{"model": "gpt"}]]
