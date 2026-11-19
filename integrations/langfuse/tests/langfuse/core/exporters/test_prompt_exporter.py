from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from unittest.mock import MagicMock

import pytest

from langfuse.core.exporters.prompt_exporter import PromptExporter, PROMPT_INCREMENTAL
from langfuse.core.options import ListPromptOptions, SinglePromptOptions


TEST_PROMPTS = [
    {
        "name": "movie-critic",
        "type": "text",
        "versions": [1, 2],
        "labels": ["production"],
        "tags": [],
        "lastUpdatedAt": "2024-07-10T10:30:00Z",
        "lastConfig": {},
    }
]


async def _async_batches(
    items: list[dict[str, Any]],
) -> AsyncGenerator[list[dict[str, Any]], None]:
    yield items


@pytest.mark.asyncio
class TestPromptExporter:
    async def test_get_single_resource(self) -> None:
        mock_client = MagicMock()
        mock_client.send_paginated_request = lambda *a, **k: _async_batches(
            TEST_PROMPTS
        )
        exporter = PromptExporter(mock_client)
        result = await exporter.get_resource(SinglePromptOptions(name="movie-critic"))
        assert result == TEST_PROMPTS[0]

    async def test_get_paginated_resources_passes_filters(self) -> None:
        captured: dict[str, Any] = {}

        async def capture(
            endpoint: str, params: dict[str, Any] | None = None, **_: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            captured["endpoint"] = endpoint
            captured["params"] = params
            yield TEST_PROMPTS

        mock_client = MagicMock()
        mock_client.send_paginated_request = capture
        exporter = PromptExporter(mock_client)
        batches = [
            b
            async for b in exporter.get_paginated_resources(
                ListPromptOptions(
                    from_updated_at="2024-01-01T00:00:00+00:00",
                    label="production",
                    tag="core",
                )
            )
        ]
        assert batches == [TEST_PROMPTS]
        assert captured["endpoint"] == "v2/prompts"
        assert captured["params"] == {
            "fromUpdatedAt": "2024-01-01T00:00:00+00:00",
            "label": "production",
            "tag": "core",
        }

    async def test_incremental_strategy_param(self) -> None:
        params = PROMPT_INCREMENTAL.build_params(
            datetime(2024, 1, 1, tzinfo=timezone.utc)
        )
        assert params["fromUpdatedAt"].startswith("2024-01-01")
