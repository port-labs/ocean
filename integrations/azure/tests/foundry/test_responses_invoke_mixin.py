from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError

from azure_integration.foundry.actions.responses_invoke_mixin import (
    INVOKE_RUNNING_STATUS_LABEL,
    MODEL_RUNNING_STATUS_LABEL,
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
    mock_ocean.port_client.post_run_log = AsyncMock()

    with patch(
        "azure_integration.foundry.actions.responses_invoke_mixin.ocean",
        mock_ocean,
    ):
        await mixin._bind_run_to_response(
            run,
            response_id="resp_1",
            bind_output={"conversationId": "conv_1"},
            running_status_label=INVOKE_RUNNING_STATUS_LABEL,
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
    mock_ocean.port_client.post_run_log.assert_awaited_once_with(
        run,
        "Waiting for agent response",
        status_label=INVOKE_RUNNING_STATUS_LABEL,
        should_raise=False,
    )
    assert run.output == {
        "conversationId": "conv_1",
        "responseId": "resp_1",
    }
    assert INVOKE_RUNNING_STATUS_LABEL == "Agent working"
    assert MODEL_RUNNING_STATUS_LABEL == "Model thinking"
    assert len(INVOKE_RUNNING_STATUS_LABEL.split()) <= 2
    assert len(MODEL_RUNNING_STATUS_LABEL.split()) <= 2


@pytest.mark.asyncio
async def test_bind_run_uses_custom_running_status_label() -> None:
    run = _workflow_run()
    mixin = ResponsesInvokeMixin()
    mock_ocean = MagicMock()
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.patch_wf_node_run = AsyncMock()
    mock_ocean.port_client.post_run_log = AsyncMock()

    with patch(
        "azure_integration.foundry.actions.responses_invoke_mixin.ocean",
        mock_ocean,
    ):
        await mixin._bind_run_to_response(
            run,
            response_id="resp_1",
            bind_output={},
            running_status_label=MODEL_RUNNING_STATUS_LABEL,
        )

    patch_body = mock_ocean.port_client.patch_wf_node_run.await_args.args[1]
    assert patch_body["statusLabel"] == {"text": MODEL_RUNNING_STATUS_LABEL}
    mock_ocean.port_client.post_run_log.assert_awaited_once_with(
        run,
        "Waiting for model response",
        status_label=MODEL_RUNNING_STATUS_LABEL,
        should_raise=False,
    )


@pytest.mark.asyncio
async def test_duplicate_stream_raises() -> None:
    run = _workflow_run()
    mixin = ResponsesInvokeMixin()
    manager = MagicMock()
    manager.track = AsyncMock(return_value=False)

    with (
        patch(
            "azure_integration.foundry.actions.responses_invoke_mixin.get_stream_manager",
            return_value=manager,
        ),
        pytest.raises(ActionExecutionError, match="already active"),
    ):
        await mixin._execute_with_sse_completion(
            run,
            invoke_url="https://example/responses",
            body={"input": "hi"},
            stream_key="dup",
            bind_output={},
            running_status_label=INVOKE_RUNNING_STATUS_LABEL,
        )
