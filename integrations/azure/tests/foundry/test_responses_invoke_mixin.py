from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from azure_integration.foundry.actions.responses_invoke_mixin import (
    INVOKE_RUNNING_STATUS_LABEL,
    ResponsesInvokeMixin,
)


def _workflow_run() -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="wfnr_1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="azure",
            integrationProvider="azure",
            integrationInvocationType="invoke_agent",
            integrationActionExecutionProperties={},
        ),
        output={"toolboxName": "port-mcps-x"},
    )


@pytest.mark.asyncio
async def test_bind_run_patches_slim_output_and_status_label() -> None:
    run = _workflow_run()
    mixin = ResponsesInvokeMixin()
    mock_ocean = MagicMock()
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.patch_wf_node_run = AsyncMock()

    with patch(
        "azure_integration.foundry.actions.responses_invoke_mixin.ocean",
        mock_ocean,
    ):
        await mixin._bind_run_to_response(
            run,
            response_id="resp_1",
            bind_output={"conversationId": "conv_1"},
        )

    mock_ocean.port_client.patch_wf_node_run.assert_awaited_once_with(
        run.id,
        {
            "status": WorkflowNodeRunStatus.IN_PROGRESS,
            "externalRunId": "resp_1",
            "output": {
                "conversationId": "conv_1",
                "responseId": "resp_1",
            },
            "statusLabel": {"text": INVOKE_RUNNING_STATUS_LABEL},
        },
    )
    assert run.output == {
        "conversationId": "conv_1",
        "responseId": "resp_1",
    }
    assert INVOKE_RUNNING_STATUS_LABEL == "Agent working"
    assert len(INVOKE_RUNNING_STATUS_LABEL.split()) <= 2
