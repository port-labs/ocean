from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError

from azure_integration.foundry.actions.cancel_response_executor import (
    RESPONSE_CANCELLED_STATUS_LABEL,
    CancelResponseExecutor,
)

_PROJECT_ARM = (
    "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.CognitiveServices/"
    "accounts/acct/projects/proj"
)


def _run(execution_properties: dict[str, object]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="azure",
            integrationProvider="azure",
            integrationInvocationType="cancel_response",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.mark.asyncio
async def test_cancel_response_posts_to_openai_cancel_route() -> None:
    client_mock = MagicMock()
    client_mock.build_url = CancelResponseExecutor().client.build_url
    client_mock.send_api_request = AsyncMock(
        return_value={"id": "resp_1", "status": "cancelled"}
    )
    executor = CancelResponseExecutor()
    executor.client = client_mock
    mock_ocean = MagicMock()
    mock_ocean.port_client.post_run_log = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    run = _run({"projectArmId": _PROJECT_ARM, "responseId": "resp_1"})

    with patch(
        "azure_integration.foundry.actions.cancel_response_executor.ocean", mock_ocean
    ):
        await executor.execute(run)

    send_call = client_mock.send_api_request.await_args
    assert send_call is not None
    url = send_call.args[0]
    assert url.endswith("/openai/v1/responses/resp_1/cancel")
    assert send_call.kwargs["method"] == "POST"
    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert (
        mock_ocean.port_client.report_run_completed.await_args.kwargs["status_label"]
        == RESPONSE_CANCELLED_STATUS_LABEL
    )
    assert run.output == {
        "responseId": "resp_1",
        "projectArmId": _PROJECT_ARM,
        "status": "cancelled",
    }


@pytest.mark.asyncio
async def test_cancel_response_partition_key_is_response_id() -> None:
    executor = CancelResponseExecutor()
    assert await executor._get_partition_key(_run({"responseId": "resp_9"})) == "resp_9"
    assert await executor._get_partition_key(_run({})) is None


@pytest.mark.asyncio
async def test_cancel_response_requires_response_id() -> None:
    executor = CancelResponseExecutor()
    with pytest.raises(ActionExecutionError, match="responseId"):
        await executor.execute(_run({"projectArmId": _PROJECT_ARM}))
