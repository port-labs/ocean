from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from azure_integration.foundry.helpers.invoke_completion import (
    complete_invoke_run_for_response,
    complete_invoke_run_from_webhook,
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


def _ocean() -> MagicMock:
    mock = MagicMock()
    mock.port_client.is_run_in_progress = MagicMock(return_value=True)
    mock.port_client.report_run_completed = AsyncMock()
    mock.port_client.post_run_log = AsyncMock()
    return mock


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("PATCH", "https://api.getport.io/v1/workflows/nodes/runs/x")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("conflict", request=request, response=response)


@pytest.mark.asyncio
async def test_complete_treats_409_as_already_done() -> None:
    run = _run("run_1")
    mock_ocean = _ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock(
        side_effect=_http_status_error(409)
    )
    with (
        patch("azure_integration.foundry.helpers.invoke_completion.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.stream_manager.get_stream_manager"
        ) as mock_manager,
    ):
        mock_manager.return_value.untrack_for_run = AsyncMock()
        assert (
            await complete_invoke_run_for_response(
                run,
                response_id="resp_1",
                response_body={"id": "resp_1", "status": "completed"},
                success=True,
                source="test",
            )
            is False
        )

    mock_ocean = _ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock(
        side_effect=RuntimeError("port down")
    )
    with (
        patch("azure_integration.foundry.helpers.invoke_completion.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.stream_manager.get_stream_manager"
        ) as mock_manager,
        pytest.raises(RuntimeError, match="port down"),
    ):
        mock_manager.return_value.untrack_for_run = AsyncMock()
        await complete_invoke_run_for_response(
            _run("run_fail"),
            response_id="resp_fail",
            response_body={"id": "resp_fail"},
            success=True,
            source="test",
        )


@pytest.mark.asyncio
async def test_webhook_answer_and_arm_id_endpoint() -> None:
    run = _run("run_wh")
    assert run.config is not None
    run.config.integrationActionExecutionProperties.update(
        {"agentId": "agent-1", "reportInvocationStatus": True}
    )
    run.output = {"responseId": "resp_wh", "conversationId": "conv_1"}
    mock_ocean = _ocean()
    get_resource = AsyncMock(
        return_value={
            "id": "resp_wh",
            "status": "completed",
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        }
    )
    with (
        patch("azure_integration.foundry.helpers.invoke_completion.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.ResponsesExporter"
        ) as exporter_cls,
        patch(
            "azure_integration.foundry.helpers.invoke_completion.create_foundry_client"
        ),
        patch(
            "azure_integration.foundry.stream_manager.get_stream_manager"
        ) as mock_manager,
    ):
        exporter_cls.return_value.get_resource = get_resource
        mock_manager.return_value.untrack_for_run = AsyncMock()
        assert await complete_invoke_run_from_webhook(
            run, event_type="response.completed", response_id="resp_wh"
        )
    assert run.output["inputTokens"] == 1
    assert run.output["outputTokens"] == 2
    assert run.output["totalTokens"] == 3

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
    get_resource = AsyncMock(
        return_value={"id": "resp_jq", "status": "completed", "usage": {}}
    )
    with (
        patch("azure_integration.foundry.helpers.invoke_completion.ocean", mock_ocean),
        patch(
            "azure_integration.foundry.helpers.invoke_completion.ResponsesExporter"
        ) as exporter_cls,
        patch(
            "azure_integration.foundry.helpers.invoke_completion.create_foundry_client"
        ),
        patch(
            "azure_integration.foundry.stream_manager.get_stream_manager"
        ) as mock_manager,
    ):
        exporter_cls.return_value.get_resource = get_resource
        mock_manager.return_value.untrack_for_run = AsyncMock()
        await complete_invoke_run_from_webhook(
            run_jq, event_type="response.completed", response_id="resp_jq"
        )
    assert get_resource.await_args is not None
    options = get_resource.await_args.args[0]
    assert (
        options.project_endpoint
        == "https://acct.services.ai.azure.com/api/projects/p"
    )
