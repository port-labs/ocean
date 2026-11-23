import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunLog,
    WorkflowNodeRunStatus,
)

from azure_integration.foundry.stream_manager import (
    ResponsesStreamManager,
    _MAX_CONCURRENT_STREAMS,
    _flush_logs,
)


def _run(run_id: str = "run-1") -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id=run_id,
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="azure",
            integrationProvider="azure",
            integrationInvocationType="invoke_agent",
            integrationActionExecutionProperties={},
        ),
    )


@pytest.mark.asyncio
async def test_track_capacity_duplicate_and_lifecycle() -> None:
    manager = ResponsesStreamManager()
    for i in range(_MAX_CONCURRENT_STREAMS):
        manager._tasks[f"key-{i}"] = MagicMock()
    assert (
        await manager.track(
            stream_key="overflow",
            invoke_url="https://example/responses",
            response_body={"input": "hi"},
            run=_run(),
        )
        == "capacity"
    )

    dup = ResponsesStreamManager()
    dup._tasks["dup"] = MagicMock()
    assert (
        await dup.track(
            stream_key="dup",
            invoke_url="https://example/responses",
            response_body={"input": "hi"},
            run=_run(),
        )
        == "duplicate"
    )

    life = ResponsesStreamManager()
    current = asyncio.current_task()
    assert current is not None
    life._tasks["self"] = current
    await life.untrack("self")
    assert not current.cancelled()

    async def _sleep_forever() -> None:
        await asyncio.Event().wait()

    life._tasks["a"] = asyncio.create_task(_sleep_forever())
    await life.shutdown()
    assert life._tasks == {}

    buffer = [WorkflowNodeRunLog(message="late", level="INFO")]
    mock_ocean = MagicMock()
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=False)
    mock_ocean.port_client.post_run_logs = AsyncMock()
    with patch("azure_integration.foundry.stream_manager.ocean", mock_ocean):
        await _flush_logs(_run(), buffer)
    mock_ocean.port_client.post_run_logs.assert_not_called()


@pytest.mark.asyncio
async def test_terminal_sse_stops() -> None:
    manager = ResponsesStreamManager()
    mock_response = MagicMock()
    mock_response.aclose = AsyncMock()

    async def _events() -> AsyncIterator[str]:
        yield 'data: {"type":"response.created","response":{"id":"resp_1"}}'
        yield 'data: {"type":"response.completed","response":{"id":"resp_1"}}'
        yield "data: [DONE]"

    mock_response.aiter_lines = MagicMock(return_value=_events())
    mock_client = MagicMock()
    mock_client.open_responses_stream = AsyncMock(return_value=mock_response)
    mock_ocean = MagicMock()
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.post_run_logs = AsyncMock()
    on_terminal = AsyncMock()
    with (
        patch(
            "azure_integration.foundry.stream_manager.create_foundry_client",
            return_value=mock_client,
        ),
        patch("azure_integration.foundry.stream_manager.ocean", mock_ocean),
    ):
        assert (
            await manager.track(
                stream_key="term",
                invoke_url="https://example/responses",
                response_body={"input": "hi"},
                run=_run(),
                stop_on_terminal_sse=True,
                on_terminal_sse=on_terminal,
            )
            == "started"
        )
        for _ in range(50):
            if "term" not in manager._tasks:
                break
            await asyncio.sleep(0.01)
    on_terminal.assert_awaited()
