import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from helpers.invoke_completion import (
    _completed_invoke_run_ids,
    complete_invoke_run_for_response,
)


@pytest.mark.asyncio
async def test_complete_invoke_run_is_idempotent() -> None:
    _completed_invoke_run_ids.clear()
    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {}
    run.output = {}
    run.is_in_progress = True

    mock_ocean = MagicMock()
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("helpers.invoke_completion.ocean", mock_ocean),
        patch("helpers.invoke_completion.register_catalog_conversation", AsyncMock()),
        patch("helpers.invoke_completion.register_catalog_response_from_body", AsyncMock()),
        patch("stream_manager.get_stream_manager") as mock_manager,
    ):
        mock_manager.return_value.untrack_for_run = AsyncMock()
        first, second = await asyncio.gather(
            complete_invoke_run_for_response(
                run,
                response_id="resp_1",
                response_body={"id": "resp_1", "status": "completed"},
                success=True,
                source="test",
            ),
            complete_invoke_run_for_response(
                run,
                response_id="resp_1",
                response_body={"id": "resp_1", "status": "completed"},
                success=True,
                source="test",
            ),
        )

    assert (first, second).count(True) == 1
    assert mock_ocean.port_client.report_run_completed.await_count == 1
