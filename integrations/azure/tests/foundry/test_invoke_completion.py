import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from azure_integration.foundry.helpers.invoke_completion import (
    _completed_invoke_run_ids,
    _completed_response_ids,
    complete_invoke_run_for_response,
    complete_invoke_run_from_webhook,
    is_response_completion_claimed,
)


def _run(run_id: str) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id=run_id,
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="azure-ai-foundry",
            integrationProvider="azure-ai-foundry",
            integrationInvocationType="invoke_agent",
            integrationActionExecutionProperties={
                "projectEndpoint": "https://x/api/projects/p",
            },
        ),
    )


def _clear() -> None:
    _completed_invoke_run_ids.clear()
    _completed_response_ids.clear()


def _ocean() -> MagicMock:
    mock = MagicMock()
    mock.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock.port_client.report_run_completed = AsyncMock()
    mock.port_client.post_run_log = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_complete_idempotent_and_unclaim_on_fail() -> None:
    _clear()
    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {}
    run.output = {}
    mock_ocean = _ocean()
    with (
        patch("azure_integration.foundry.helpers.invoke_completion.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.register_catalog_rows",
            AsyncMock(),
        ),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.response_body_for_catalog",
            AsyncMock(
                return_value={"id": "resp_1", "status": "completed", "usage": {}}
            ),
        ),
        patch(
            "azure_integration.foundry.stream_manager.get_stream_manager"
        ) as mock_manager,
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

    _clear()
    fail_run = _run("run_fail")
    mock_ocean = _ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock(
        side_effect=RuntimeError("port down")
    )
    with (
        patch("azure_integration.foundry.helpers.invoke_completion.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.response_body_for_catalog",
            AsyncMock(return_value={"id": "resp_fail", "status": "completed"}),
        ),
        patch(
            "azure_integration.foundry.stream_manager.get_stream_manager"
        ) as mock_manager,
        pytest.raises(RuntimeError, match="port down"),
    ):
        mock_manager.return_value.untrack_for_run = AsyncMock()
        await complete_invoke_run_for_response(
            fail_run,
            response_id="resp_fail",
            response_body={"id": "resp_fail"},
            success=True,
            source="test",
        )
    assert not is_response_completion_claimed("resp_fail")


@pytest.mark.asyncio
async def test_webhook_answer_arm_id_and_skip_claimed() -> None:
    _clear()
    run = _run("run_wh")
    assert run.config is not None
    run.config.integrationActionExecutionProperties.update(
        {"agentId": "agent-1", "reportInvocationStatus": True}
    )
    run.output = {"responseId": "resp_wh", "conversationId": "conv_1"}
    mock_ocean = _ocean()
    with (
        patch("azure_integration.foundry.helpers.invoke_completion.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.register_catalog_rows",
            AsyncMock(),
        ),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.response_body_for_catalog",
            AsyncMock(
                return_value={
                    "id": "resp_wh",
                    "status": "completed",
                    "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": "webhook answer"}
                            ],
                        }
                    ],
                }
            ),
        ),
        patch(
            "azure_integration.foundry.stream_manager.get_stream_manager"
        ) as mock_manager,
    ):
        mock_manager.return_value.untrack_for_run = AsyncMock()
        assert await complete_invoke_run_from_webhook(
            run, event_type="response.completed", response_id="resp_wh"
        )
    assert run.output["answer"] == "webhook answer"
    mock_ocean.port_client.post_run_log.assert_awaited_once()

    _completed_response_ids["resp_done"] = None
    assert (
        await complete_invoke_run_from_webhook(
            MagicMock(id="x", execution_properties={}),
            event_type="response.completed",
            response_id="resp_done",
        )
        is False
    )

    _clear()
    run_jq = _run("run_jq")
    arm_id = (
        "/subscriptions/s/resourceGroups/rg/providers/"
        "Microsoft.CognitiveServices/accounts/acct/projects/p"
    )
    assert run_jq.config is not None
    run_jq.config.integrationActionExecutionProperties = {
        "projectArmId": "{{ .outputs.fetch_agent.projectId }}",
    }
    run_jq.output = {"responseId": "resp_jq", "projectArmId": arm_id}
    mock_ocean = _ocean()
    fetch = AsyncMock(
        return_value={"id": "resp_jq", "status": "completed", "usage": {}}
    )
    with (
        patch("azure_integration.foundry.helpers.invoke_completion.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.register_catalog_rows",
            AsyncMock(),
        ),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.response_body_for_catalog",
            fetch,
        ),
        patch(
            "azure_integration.foundry.stream_manager.get_stream_manager"
        ) as mock_manager,
    ):
        mock_manager.return_value.untrack_for_run = AsyncMock()
        await complete_invoke_run_from_webhook(
            run_jq, event_type="response.completed", response_id="resp_jq"
        )
    assert fetch.await_args is not None
    assert (
        fetch.await_args.kwargs["project_endpoint"]
        == "https://acct.services.ai.azure.com/api/projects/p"
    )
