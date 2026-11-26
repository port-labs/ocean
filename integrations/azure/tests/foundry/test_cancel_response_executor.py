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
    run = _run(
        {
            "projectArmId": _PROJECT_ARM,
            "agentId": "agent-1",
            "responseId": "resp_1",
        }
    )

    with patch(
        "azure_integration.foundry.actions.cancel_response_executor.ocean", mock_ocean
    ):
        await executor.execute(run)

    send_call = client_mock.send_api_request.await_args
    assert send_call is not None
    url = send_call.args[0]
    assert url.endswith(
        "agents/agent-1/endpoint/protocols/openai/responses/resp_1/cancel"
    )
    assert send_call.kwargs["method"] == "POST"
    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert (
        mock_ocean.port_client.report_run_completed.await_args.kwargs["status_label"]
        == RESPONSE_CANCELLED_STATUS_LABEL
    )
    assert run.output == {
        "responseId": "resp_1",
        "responseIds": ["resp_1"],
        "projectArmId": _PROJECT_ARM,
        "status": "cancelled",
    }


@pytest.mark.asyncio
async def test_cancel_response_partition_key_is_response_id() -> None:
    executor = CancelResponseExecutor()
    assert await executor._get_partition_key(_run({"responseId": "resp_9"})) == "resp_9"
    assert await executor._get_partition_key(_run({})) is None


@pytest.mark.asyncio
async def test_cancel_response_requires_target() -> None:
    executor = CancelResponseExecutor()
    with pytest.raises(ActionExecutionError, match="responseId"):
        await executor.execute(
            _run({"projectArmId": _PROJECT_ARM, "agentId": "agent-1"})
        )


@pytest.mark.asyncio
async def test_cancel_response_cancels_all_in_flight_for_conversation() -> None:
    client_mock = MagicMock()
    client_mock.build_url = CancelResponseExecutor().client.build_url

    async def _pages(*_args: object, **_kwargs: object):
        yield [
            {
                "id": "resp_a",
                "status": "in_progress",
                "conversation": {"id": "conv_1"},
            },
            {
                "id": "resp_b",
                "status": "queued",
                "conversation": {"id": "conv_1"},
            },
            {
                "id": "resp_done",
                "status": "completed",
                "conversation": {"id": "conv_1"},
            },
        ]

    client_mock.send_cursor_paginated_request = MagicMock(return_value=_pages())
    client_mock.send_api_request = AsyncMock(
        return_value={"status": "cancelled"}
    )
    executor = CancelResponseExecutor()
    executor.client = client_mock
    mock_ocean = MagicMock()
    mock_ocean.port_client.post_run_log = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    run = _run(
        {
            "projectArmId": _PROJECT_ARM,
            "agentId": "agent-1",
            "conversationId": "conv_1",
        }
    )

    with patch(
        "azure_integration.foundry.actions.cancel_response_executor.ocean", mock_ocean
    ):
        await executor.execute(run)

    assert client_mock.send_api_request.await_count == 2
    urls = [c.args[0] for c in client_mock.send_api_request.await_args_list]
    agent_prefix = "agents/agent-1/endpoint/protocols/openai/responses/"
    assert any(u.endswith(f"{agent_prefix}resp_a/cancel") for u in urls)
    assert any(u.endswith(f"{agent_prefix}resp_b/cancel") for u in urls)
    assert run.output["responseIds"] == ["resp_a", "resp_b"]
