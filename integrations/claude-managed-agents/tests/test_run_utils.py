from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowNodeRun,
    WorkflowNodeRunResult,
    WorkflowNodeRunStatus,
)

from webhook_processors.trigger_agent_webhook_processor import TriggerAgentWebhookProcessor

_complete_port_run = TriggerAgentWebhookProcessor._complete_port_run


@pytest.mark.asyncio
async def test_complete_port_run_merges_extra_output_for_workflow_nodes() -> None:
    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {"sessionId": "s1"}

    mock_ocean = MagicMock()
    mock_ocean.port_client.patch_wf_node_run = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean):
        await _complete_port_run(run, True, extra_output={"response": "done"})

    mock_ocean.port_client.patch_wf_node_run.assert_awaited_once_with(
        "run_1",
        {
            "status": WorkflowNodeRunStatus.COMPLETED,
            "result": WorkflowNodeRunResult.SUCCESS,
            "output": {"sessionId": "s1", "response": "done"},
        },
    )
    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_port_run_delegates_without_extra_output() -> None:
    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}

    mock_ocean = MagicMock()
    mock_ocean.port_client.patch_wf_node_run = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with patch("webhook_processors.trigger_agent_webhook_processor.ocean", mock_ocean):
        await _complete_port_run(run, False)

    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(run, False)
    mock_ocean.port_client.patch_wf_node_run.assert_not_awaited()
