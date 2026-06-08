import pytest
from unittest.mock import MagicMock
from collections.abc import AsyncGenerator

from core.exporters.ai_commit_metrics_exporter import CursorAiCommitMetricsExporter


@pytest.mark.asyncio
async def test_ai_commit_exporter_yields_batches() -> None:
    mock_client = MagicMock()

    async def _gen(
        _options: dict[str, object]
    ) -> AsyncGenerator[list[dict[str, str]], None]:
        yield [{"commitHash": "abc"}]

    mock_client.get_ai_commit_metrics = _gen
    exporter = CursorAiCommitMetricsExporter(mock_client)

    batches = [
        batch
        async for batch in exporter.get_paginated_resources(
            {"startDate": "30d", "endDate": "0d", "page": 1, "pageSize": 100}
        )
    ]

    assert batches == [[{"commitHash": "abc"}]]
