import pytest
from unittest.mock import MagicMock
from collections.abc import AsyncGenerator

from core.exporters.team_model_usage_exporter import CursorTeamModelUsageExporter
from core.exporters.user_model_usage_exporter import CursorUserModelUsageExporter


@pytest.mark.asyncio
async def test_team_model_usage_exporter_yields_batches() -> None:
    mock_client = MagicMock()

    async def _gen(
        _options: dict[str, object]
    ) -> AsyncGenerator[list[dict[str, str]], None]:
        yield [{"date": "2026-05-10"}]

    mock_client.get_team_model_usage = _gen
    exporter = CursorTeamModelUsageExporter(mock_client)

    batches = [
        batch
        async for batch in exporter.get_paginated_resources(
            {"startDate": "30d", "endDate": "0d", "page": 1, "pageSize": 500}
        )
    ]

    assert batches == [[{"date": "2026-05-10"}]]


@pytest.mark.asyncio
async def test_user_model_usage_exporter_yields_batches() -> None:
    mock_client = MagicMock()

    async def _gen(
        _options: dict[str, object]
    ) -> AsyncGenerator[list[dict[str, str]], None]:
        yield [{"userEmail": "a@port.io"}]

    mock_client.get_user_model_usage = _gen
    exporter = CursorUserModelUsageExporter(mock_client)

    batches = [
        batch
        async for batch in exporter.get_paginated_resources(
            {"startDate": "30d", "endDate": "0d", "page": 1, "pageSize": 50}
        )
    ]

    assert batches == [[{"userEmail": "a@port.io"}]]
