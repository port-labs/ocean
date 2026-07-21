from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import WorkflowNodeRun

from webhook_processors.utils import (
    extract_port_run_id_from_request,
    parse_webhook_timestamp,
    resolve_cursor_run_id_from_runs,
    resolve_cursor_run_id_for_webhook,
    resolve_tracked_run,
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


def test_resolve_cursor_run_id_from_runs_picks_newest_before_webhook_time() -> None:
    webhook_time = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    runs = [
        {
            "id": "run-new",
            "createdAt": "2025-06-01T13:00:00Z",
        },
        {
            "id": "run-old",
            "createdAt": "2025-06-01T11:00:00Z",
        },
    ]

    assert resolve_cursor_run_id_from_runs(runs, webhook_time) == "run-old"


@pytest.mark.asyncio
async def test_resolve_cursor_run_id_for_webhook_uses_first_list_page() -> None:
    client_mock = MagicMock()
    client_mock.page_size = 20
    client_mock.send_api_request = AsyncMock(
        return_value={"items": [{"id": "run-1", "createdAt": "2025-06-01T11:00:00Z"}]}
    )
    webhook_time = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)

    cursor_run_id = await resolve_cursor_run_id_for_webhook(
        "bc-1", webhook_time, client=client_mock
    )

    assert cursor_run_id == "run-1"
    client_mock.send_api_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_tracked_run_prefers_cursor_run_id_for_follow_up() -> None:
    create_run = MagicMock(spec=WorkflowNodeRun)
    create_run.id = "create_run"
    create_run.output = {"agentId": "bc-1"}

    follow_up_run = MagicMock(spec=WorkflowNodeRun)
    follow_up_run.id = "follow_up_run"
    follow_up_run.output = {"agentId": "bc-1"}

    mock_ocean = MagicMock()

    async def _find_external_id(external_id: str) -> WorkflowNodeRun | None:
        if external_id == "cursor-run-2":
            return follow_up_run
        if external_id == "bc-1":
            return create_run
        return None

    mock_ocean.port_client.find_run_by_external_id = AsyncMock(
        side_effect=_find_external_id
    )
    mock_ocean.port_client.is_run_in_progress.side_effect = (
        lambda run: run.id == "follow_up_run"
    )

    with patch("webhook_processors.utils.ocean", mock_ocean):
        resolved = await resolve_tracked_run("bc-1", "cursor-run-2")

    assert resolved is follow_up_run
    mock_ocean.port_client.find_run_by_external_id.assert_awaited_once_with(
        "cursor-run-2"
    )


@pytest.mark.asyncio
async def test_resolve_tracked_run_falls_back_to_agent_id_for_create() -> None:
    create_run = MagicMock(spec=WorkflowNodeRun)
    create_run.id = "create_run"
    create_run.output = {"agentId": "bc-1"}

    mock_ocean = MagicMock()

    async def _find_external_id(external_id: str) -> WorkflowNodeRun | None:
        if external_id == "cursor-run-1":
            return None
        if external_id == "bc-1":
            return create_run
        return None

    mock_ocean.port_client.find_run_by_external_id = AsyncMock(
        side_effect=_find_external_id
    )
    mock_ocean.port_client.is_run_in_progress.return_value = True

    with patch("webhook_processors.utils.ocean", mock_ocean):
        resolved = await resolve_tracked_run("bc-1", "cursor-run-1")

    assert resolved is create_run
    assert [
        call.args[0]
        for call in mock_ocean.port_client.find_run_by_external_id.await_args_list
    ] == ["cursor-run-1", "bc-1"]
