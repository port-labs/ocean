import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunLog,
    WorkflowNodeRunStatus,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError

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
async def test_track_raises_at_capacity() -> None:
    manager = ResponsesStreamManager()
    run = _run()
    for i in range(_MAX_CONCURRENT_STREAMS):
        manager._tasks[f"key-{i}"] = MagicMock()

    with (
        patch(
            "azure_integration.foundry.stream_manager.create_foundry_client",
            return_value=MagicMock(),
        ),
        pytest.raises(ActionExecutionError, match="Too many concurrent"),
    ):
        await manager.track(
            stream_key="overflow",
            invoke_url="https://example/responses",
            response_body={"input": "hi"},
            run=run,
        )


@pytest.mark.asyncio
async def test_track_rejects_duplicate_key() -> None:
    manager = ResponsesStreamManager()
    manager._tasks["dup"] = MagicMock()
    assert (
        await manager.track(
            stream_key="dup",
            invoke_url="https://example/responses",
            response_body={"input": "hi"},
            run=_run(),
        )
        is False
    )


@pytest.mark.asyncio
async def test_untrack_skips_cancel_for_current_task() -> None:
    manager = ResponsesStreamManager()
    current = asyncio.current_task()
    assert current is not None
    manager._tasks["self"] = current
    await manager.untrack("self")
    assert "self" not in manager._tasks
    assert not current.cancelled()


@pytest.mark.asyncio
async def test_untrack_cancels_other_task() -> None:
    manager = ResponsesStreamManager()

    async def _sleep_forever() -> None:
        await asyncio.Event().wait()

    task = asyncio.create_task(_sleep_forever())
    manager._tasks["other"] = task
    await manager.untrack("other")
    assert "other" not in manager._tasks
    assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_flush_logs_skips_when_run_not_in_progress() -> None:
    run = _run()
    buffer = [WorkflowNodeRunLog(message="late", level="INFO")]
    mock_ocean = MagicMock()
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=False)
    mock_ocean.port_client.post_run_logs = AsyncMock()
    with patch("azure_integration.foundry.stream_manager.ocean", mock_ocean):
        await _flush_logs(run, buffer)
    assert buffer == []
    mock_ocean.port_client.post_run_logs.assert_not_called()


@pytest.mark.asyncio
async def test_shutdown_untracks_all() -> None:
    manager = ResponsesStreamManager()

    async def _sleep_forever() -> None:
        await asyncio.Event().wait()

    manager._tasks["a"] = asyncio.create_task(_sleep_forever())
    manager._tasks["b"] = asyncio.create_task(_sleep_forever())
    await manager.shutdown()
    assert manager._tasks == {}
