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


def _run() -> WorkflowNodeRun:
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
    )


@pytest.mark.asyncio
async def test_bind_and_capacity_fallback() -> None:
    run = _run()
    mixin = ResponsesInvokeMixin(MagicMock())
    mock_ocean = MagicMock()
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.patch_wf_node_run = AsyncMock()
    mock_ocean.port_client.post_run_log = AsyncMock()

    with patch(
        "azure_integration.foundry.actions.responses_invoke_mixin.ocean", mock_ocean
    ):
        await mixin._bind_run_to_response(
            run,
            response_id="resp_1",
            bind_output={"conversationId": "conv_1"},
            running_status_label=INVOKE_RUNNING_STATUS_LABEL,
        )
        await mixin._bind_run_to_response(
            run,
            response_id="resp_2",
            bind_output={},
            running_status_label=MODEL_RUNNING_STATUS_LABEL,
        )

    assert mock_ocean.port_client.patch_wf_node_run.await_count == 2
    assert "Waiting for model response" in str(
        mock_ocean.port_client.post_run_log.await_args_list[-1]
    )

    mixin.client = MagicMock()
    mixin.client.send_api_request = AsyncMock(
        return_value={"id": "resp_cap", "status": "in_progress"}
    )
    manager = MagicMock()
    manager.track = AsyncMock(return_value="capacity")
    with (
        patch(
            "azure_integration.foundry.actions.responses_invoke_mixin.ocean", mock_ocean
        ),
        patch(
            "azure_integration.foundry.actions.responses_invoke_mixin.get_stream_manager",
            return_value=manager,
        ),
        patch(
            "azure_integration.foundry.actions.responses_invoke_mixin.complete_invoke_run_for_response",
            AsyncMock(return_value=True),
        ),
    ):
        await mixin.execute_responses_invoke(
            run,
            invoke_label="Invoking",
            invoke_url="https://example/responses",
            body={"input": "hi"},
            stream_key="cap",
            bind_output={},
            running_status_label=INVOKE_RUNNING_STATUS_LABEL,
            early_complete_on_bind=True,
        )
    mixin.client.send_api_request.assert_awaited_once()

    manager.track = AsyncMock(return_value="duplicate")
    with (
        patch(
            "azure_integration.foundry.actions.responses_invoke_mixin.ocean", mock_ocean
        ),
        patch(
            "azure_integration.foundry.actions.responses_invoke_mixin.get_stream_manager",
            return_value=manager,
        ),
        pytest.raises(ActionExecutionError, match="already active"),
    ):
        await mixin.execute_responses_invoke(
            run,
            invoke_label="Invoking",
            invoke_url="https://example/responses",
            body={"input": "hi"},
            stream_key="dup",
            bind_output={},
            running_status_label=INVOKE_RUNNING_STATUS_LABEL,
        )
