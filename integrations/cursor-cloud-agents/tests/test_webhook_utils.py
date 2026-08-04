from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from webhook_processors.utils import (
    extract_port_run_id_from_request,
    parse_webhook_timestamp,
    resolve_newest_run_id_at_or_before,
)


def test_extract_port_run_id_from_path_params() -> None:
    request = MagicMock()
    request.path_params = {"run_id": "run_1"}
    assert extract_port_run_id_from_request(request) == "run_1"


def test_extract_port_run_id_returns_none_without_path_params() -> None:
    request = MagicMock(spec=[])
    assert extract_port_run_id_from_request(request) is None


def test_parse_webhook_timestamp_uses_payload_value() -> None:
    parsed = parse_webhook_timestamp(
        {"timestamp": "2025-06-01T12:00:00Z", "id": "bc-1", "status": "FINISHED"}
    )
    assert parsed == datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_resolve_newest_run_id_at_or_before_uses_first_list_page() -> None:
    runs_exporter_mock = MagicMock()
    runs_exporter_mock.list_first_page = AsyncMock(
        return_value=[
            {"id": "run-new", "createdAt": "2025-06-01T13:00:00Z"},
            {"id": "run-old", "createdAt": "2025-06-01T11:00:00Z"},
        ]
    )
    webhook_time = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)

    with patch(
        "webhook_processors.utils.create_runs_exporter",
        return_value=runs_exporter_mock,
    ):
        cursor_run_id = await resolve_newest_run_id_at_or_before("bc-1", webhook_time)

    assert cursor_run_id == "run-old"
    runs_exporter_mock.list_first_page.assert_awaited_once_with("bc-1")
