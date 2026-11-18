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


def _workflow_run(run_id: str) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id=run_id,
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="azure-ai-foundry",
            integrationProvider="azure-ai-foundry",
            integrationInvocationType="invoke_agent",
            integrationActionExecutionProperties={},
        ),
    )


def _clear_completion_caches() -> None:
    _completed_invoke_run_ids.clear()
    _completed_response_ids.clear()


@pytest.mark.asyncio
async def test_complete_unclaims_when_port_report_fails() -> None:
    _clear_completion_caches()
    run = _workflow_run("run_fail_report")
    run.config.integrationActionExecutionProperties = {
        "projectEndpoint": "https://x/api/projects/p",
    }
    mock_ocean = MagicMock()
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
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
            run,
            response_id="resp_fail",
            response_body={"id": "resp_fail"},
            success=True,
            source="test",
        )
    assert not is_response_completion_claimed("resp_fail")
    assert "run_fail_report" not in _completed_invoke_run_ids


@pytest.mark.asyncio
async def test_complete_invoke_run_is_idempotent() -> None:
    _clear_completion_caches()
    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {}
    run.output = {}
    run.is_in_progress = True

    mock_ocean = MagicMock()
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("azure_integration.foundry.helpers.invoke_completion.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.register_catalog_rows",
            AsyncMock(),
        ),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.register_catalog_response_from_body",
            AsyncMock(return_value=True),
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
    assert mock_ocean.port_client.report_run_completed.await_count == 1


@pytest.mark.asyncio
async def test_complete_invoke_run_omits_entity_link_and_noise() -> None:
    _clear_completion_caches()
    run = _workflow_run("run_2")
    run.config.integrationActionExecutionProperties = {
        "projectEndpoint": "https://x/api/projects/p",
    }
    arm_id = (
        "/subscriptions/s/resourceGroups/rg/providers/"
        "Microsoft.CognitiveServices/accounts/a/projects/p"
    )
    run.output = {
        "conversationId": "conv_keep",
        "toolboxName": "noise",
        "projectArmId": arm_id,
    }

    mock_ocean = MagicMock()
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.port_client.patch_wf_node_run = AsyncMock()

    with (
        patch("azure_integration.foundry.helpers.invoke_completion.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.register_catalog_rows",
            AsyncMock(),
        ),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.register_catalog_response_from_body",
            AsyncMock(return_value=True),
        ),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.response_body_for_catalog",
            AsyncMock(
                return_value={
                    "id": "resp_1",
                    "status": "completed",
                    "model": "gpt",
                    "usage": {},
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "hi"}],
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
        await complete_invoke_run_for_response(
            run,
            response_id="resp_1",
            response_body={"id": "resp_1", "status": "completed"},
            success=True,
            source="test",
            register_catalog=True,
        )

    assert run.output == {
        "conversationId": "conv_keep",
        "toolboxName": "noise",
        "projectArmId": arm_id,
        "responseId": "resp_1",
        "answer": "hi",
    }
    mock_ocean.port_client.patch_wf_node_run.assert_not_called()


@pytest.mark.asyncio
async def test_sse_success_registers_catalog_and_usage() -> None:
    _clear_completion_caches()
    run = _workflow_run("run_3")
    run.config.integrationActionExecutionProperties = {
        "projectEndpoint": "https://x/api/projects/p",
    }
    run.output = {"responseId": "resp_1"}

    mock_ocean = MagicMock()
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.port_client.patch_wf_node_run = AsyncMock()

    register = AsyncMock(return_value=True)
    with (
        patch("azure_integration.foundry.helpers.invoke_completion.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.register_catalog_response_from_body",
            register,
        ),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.register_catalog_rows",
            AsyncMock(),
        ),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.response_body_for_catalog",
            AsyncMock(
                return_value={
                    "id": "resp_1",
                    "model": "gpt",
                    "status": "completed",
                    "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
                }
            ),
        ),
        patch(
            "azure_integration.foundry.stream_manager.get_stream_manager"
        ) as mock_manager,
    ):
        mock_manager.return_value.untrack_for_run = AsyncMock()
        await complete_invoke_run_for_response(
            run,
            response_id="resp_1",
            response_body={"id": "resp_1"},
            success=True,
            source="SSE",
            register_catalog=True,
        )

    register.assert_awaited_once()
    assert is_response_completion_claimed("resp_1")
    assert run.output == {
        "responseId": "resp_1",
        "inputTokens": 1,
        "outputTokens": 2,
        "totalTokens": 3,
    }
    assert "model" not in run.output
    assert "responseStatus" not in run.output
    assert "responseEntityLink" not in run.output


@pytest.mark.asyncio
async def test_webhook_skips_when_response_already_claimed() -> None:
    _clear_completion_caches()
    _completed_response_ids["resp_done"] = None
    run = MagicMock()
    run.id = "run_4"
    run.execution_properties = {"projectEndpoint": "https://x/api/projects/p"}

    mock_ocean = MagicMock()
    with (
        patch("azure_integration.foundry.helpers.invoke_completion.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.response_body_for_catalog",
            AsyncMock(),
        ) as fetch,
    ):
        assert (
            await complete_invoke_run_from_webhook(
                run, event_type="response.completed", response_id="resp_done"
            )
            is False
        )
    fetch.assert_not_awaited()
    mock_ocean.port_client.report_run_completed.assert_not_called()


@pytest.mark.asyncio
async def test_complete_invoke_uses_bound_project_arm_id_over_jq_props() -> None:
    _clear_completion_caches()
    run = _workflow_run("run_jq")
    arm_id = (
        "/subscriptions/s/resourceGroups/rg/providers/"
        "Microsoft.CognitiveServices/accounts/acct/projects/p"
    )
    run.config.integrationActionExecutionProperties = {
        "projectArmId": "{{ .outputs.fetch_agent.projectId }}",
    }
    run.output = {"responseId": "resp_jq", "projectArmId": arm_id}

    mock_ocean = MagicMock()
    mock_ocean.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock_ocean.port_client.report_run_completed = AsyncMock()

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
            "azure_integration.foundry.helpers.invoke_completion.register_catalog_response_from_body",
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
            run, event_type="response.completed", response_id="resp_jq"
        )
        # Option C: webhook untracks stream (flush via cancel) before complete.
        mock_manager.return_value.untrack_for_run.assert_awaited_once_with(run.id)

    fetch.assert_awaited_once()
    assert (
        fetch.await_args.kwargs["project_endpoint"]
        == "https://acct.services.ai.azure.com/api/projects/p"
    )
    mock_ocean.port_client.report_run_completed.assert_awaited_once()
