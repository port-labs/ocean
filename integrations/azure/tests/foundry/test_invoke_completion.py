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
async def test_complete_invoke_run_sets_response_entity_link_when_registered() -> None:
    _clear_completion_caches()
    run = _workflow_run("run_2")

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
            "azure_integration.foundry.helpers.invoke_completion._foundry_response_entity_page_url",
            return_value="http://localhost:3000/foundry_responseEntity?identifier=resp_1",
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
        await complete_invoke_run_for_response(
            run,
            response_id="resp_1",
            response_body={"id": "resp_1", "status": "completed"},
            success=True,
            source="test",
            register_catalog=True,
        )

    assert run.output["responseEntityLink"] == (
        "http://localhost:3000/foundry_responseEntity?identifier=resp_1"
    )


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
    assert run.output["inputTokens"] == 1
    assert run.output["outputTokens"] == 2
    assert run.output["totalTokens"] == 3
    assert run.output["model"] == "gpt"
    assert run.output["responseStatus"] == "completed"


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
