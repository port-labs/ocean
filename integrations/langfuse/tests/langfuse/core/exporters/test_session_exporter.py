from unittest.mock import AsyncMock, MagicMock

import pytest

from langfuse.core.exporters.session_exporter import SessionExporter
from langfuse.core.options import ListSessionOptions, SingleSessionOptions


async def _pages(*batches):
    for batch in batches:
        yield batch


@pytest.mark.asyncio
class TestSessionExporter:
    async def test_get_paginated_resources_groups_by_session_id(self) -> None:
        mock_client = MagicMock()
        mock_client.send_cursor_paginated_request = lambda *a, **k: _pages(
            [
                {
                    "sessionId": "conv_a",
                    "startTime": "2026-11-16T10:00:00Z",
                    "environment": "default",
                    "userId": "u1",
                    "projectId": "p1",
                },
                {
                    "sessionId": "conv_a",
                    "startTime": "2026-11-16T10:05:00Z",
                    "environment": "default",
                    "userId": "u1",
                    "projectId": "p1",
                },
                {
                    "sessionId": "conv_b",
                    "startTime": "2026-11-16T11:00:00Z",
                    "projectId": "p1",
                },
                {"sessionId": None, "startTime": "2026-11-16T12:00:00Z"},
            ]
        )
        exporter = SessionExporter(mock_client)
        batches = [
            b
            async for b in exporter.get_paginated_resources(
                ListSessionOptions(from_start_time="2026-11-01T00:00:00Z")
            )
        ]
        assert len(batches) == 1
        by_id = {s["id"]: s for s in batches[0]}
        assert by_id["conv_a"]["createdAt"] == "2026-11-16T10:00:00Z"
        assert by_id["conv_a"]["updatedAt"] == "2026-11-16T10:05:00Z"
        assert by_id["conv_b"]["id"] == "conv_b"
        assert "None" not in by_id

    async def test_get_resource(self) -> None:
        mock_client = MagicMock()
        mock_client.send_cursor_paginated_request = lambda *a, **k: _pages(
            [
                {
                    "sessionId": "conv_a",
                    "startTime": "2026-11-16T10:00:00Z",
                    "projectId": "p1",
                }
            ]
        )
        exporter = SessionExporter(mock_client)
        result = await exporter.get_resource(
            SingleSessionOptions(session_id="conv_a", lookback_days=3)
        )
        assert result == {
            "id": "conv_a",
            "createdAt": "2026-11-16T10:00:00Z",
            "updatedAt": "2026-11-16T10:00:00Z",
            "environment": None,
            "userId": None,
            "projectId": "p1",
        }

    async def test_get_resource_missing(self) -> None:
        mock_client = MagicMock()
        mock_client.send_cursor_paginated_request = lambda *a, **k: _pages([])
        exporter = SessionExporter(mock_client)
        assert (
            await exporter.get_resource(SingleSessionOptions(session_id="missing"))
            is None
        )
