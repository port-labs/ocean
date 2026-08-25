from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from azure_devops.actions.exceptions import (
    InvalidActionParametersError,
    TriggerPipelineError,
)
from azure_devops.actions.trigger_pipeline_executor import TriggerPipelineExecutor
from azure_devops.client.azure_devops_client import RunPipelineOptions
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)
from port_ocean.context.ocean import PortOceanContext


def _make_run(props: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="trigger_pipeline"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="trigger_pipeline",
            integrationActionExecutionProperties=props,
        ),
    )


@pytest.fixture
def client() -> MagicMock:
    mock = MagicMock()
    mock.get_single_project = AsyncMock()
    mock.run_pipeline = AsyncMock()
    return mock


@pytest.fixture
def executor(client: MagicMock) -> TriggerPipelineExecutor:
    instance = TriggerPipelineExecutor()
    instance._client = client
    return instance


def _make_mock_ocean() -> MagicMock:
    mock_ocean = MagicMock()
    mock_ocean.port_client.update_run_started = AsyncMock()
    mock_ocean.port_client.post_run_log = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    return mock_ocean


@pytest.mark.asyncio
async def test_execute_missing_pipeline_id_raises(
    executor: TriggerPipelineExecutor,
) -> None:
    with pytest.raises(InvalidActionParametersError):
        await executor.execute(_make_run({"project": "proj"}))


@pytest.mark.asyncio
async def test_execute_triggers_pipeline_and_marks_started(
    executor: TriggerPipelineExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.get_single_project.return_value = {"id": "proj-guid"}
    client.run_pipeline.return_value = {
        "id": 4567,
        "_links": {
            "web": {
                "href": "https://dev.azure.com/org/proj/_build/results?buildId=4567"
            }
        },
    }
    mock_ocean = _make_mock_ocean()
    monkeypatch.setattr(
        "azure_devops.actions.trigger_pipeline_executor.ocean", mock_ocean
    )

    run = _make_run(
        {
            "project": "My Project",
            "pipelineId": "12",
            "branch": "main",
            "templateParameters": {"env": "prod"},
            "reportPipelineStatus": True,
        }
    )
    await executor.execute(run)

    client.get_single_project.assert_awaited_once_with("My Project")
    run_pipeline_call = client.run_pipeline.await_args
    assert run_pipeline_call is not None
    assert run_pipeline_call.args[0] == "proj-guid"
    assert run_pipeline_call.args[1] == "12"
    options = run_pipeline_call.args[2]
    assert isinstance(options, RunPipelineOptions)
    assert options.branch == "main"
    assert options.template_parameters == {"env": "prod"}

    started_call = mock_ocean.port_client.update_run_started.await_args
    assert started_call is not None
    assert started_call.args[0] is run
    assert (
        started_call.args[1]
        == "https://dev.azure.com/org/proj/_build/results?buildId=4567"
    )
    assert started_call.args[2] == "ado_proj-guid_12_4567"
    assert mock_ocean.port_client.post_run_log.await_count == 2
    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_project_not_found_raises(
    executor: TriggerPipelineExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.get_single_project.return_value = None
    monkeypatch.setattr(
        "azure_devops.actions.trigger_pipeline_executor.ocean", _make_mock_ocean()
    )

    with pytest.raises(InvalidActionParametersError) as exc_info:
        await executor.execute(_make_run({"project": "missing", "pipelineId": "12"}))

    assert "was not found" in str(exc_info.value)
    client.run_pipeline.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_wraps_http_error_as_trigger_pipeline_error(
    executor: TriggerPipelineExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.get_single_project.return_value = {"id": "proj-guid"}
    client.run_pipeline.side_effect = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("POST", "https://dev.azure.com"),
        response=httpx.Response(status_code=400, json={"message": "bad pipeline"}),
    )
    monkeypatch.setattr(
        "azure_devops.actions.trigger_pipeline_executor.ocean", _make_mock_ocean()
    )

    with pytest.raises(TriggerPipelineError) as exc_info:
        await executor.execute(_make_run({"project": "proj", "pipelineId": "12"}))

    assert "bad pipeline" in str(exc_info.value)


@pytest.mark.asyncio
async def test_identity_run_uses_user_token_client(
    executor: TriggerPipelineExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.get_single_project.return_value = {"id": "proj-guid"}
    client._organization_base_url = "https://dev.azure.com/myorg"
    client.webhook_auth_username = "webhook-user"
    client.excluded_tags = ["skip"]

    user_pipeline_client = MagicMock()
    user_pipeline_client.run_pipeline = AsyncMock(
        return_value={
            "id": 99,
            "_links": {"web": {"href": "https://dev.azure.com/run/99"}},
        }
    )
    mock_client_for_token = MagicMock(return_value=user_pipeline_client)
    monkeypatch.setattr(executor, "_client_for_token", mock_client_for_token)
    monkeypatch.setattr(
        "azure_devops.actions.trigger_pipeline_executor.resolve_user_token",
        AsyncMock(return_value="entra-user-token"),
    )
    mock_ocean = _make_mock_ocean()
    monkeypatch.setattr(
        "azure_devops.actions.trigger_pipeline_executor.ocean", mock_ocean
    )

    await executor.execute(_make_run({"project": "proj", "pipelineId": "12"}))

    mock_client_for_token.assert_called_once_with("entra-user-token")
    user_pipeline_client.run_pipeline.assert_awaited_once()
    client.run_pipeline.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_identity_run_uses_default_client(
    executor: TriggerPipelineExecutor,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.get_single_project.return_value = {"id": "proj-guid"}
    client.run_pipeline.return_value = {"id": 1, "_links": {}}
    monkeypatch.setattr(
        "azure_devops.actions.trigger_pipeline_executor.resolve_user_token",
        AsyncMock(return_value=None),
    )
    mock_client_for_token = MagicMock()
    monkeypatch.setattr(executor, "_client_for_token", mock_client_for_token)
    monkeypatch.setattr(
        "azure_devops.actions.trigger_pipeline_executor.ocean", _make_mock_ocean()
    )

    await executor.execute(_make_run({"project": "proj", "pipelineId": "12"}))

    mock_client_for_token.assert_not_called()
    client.run_pipeline.assert_awaited_once()


def test_client_for_token_builds_azure_devops_client_with_bearer_auth(
    executor: TriggerPipelineExecutor,
    client: MagicMock,
    mock_context: PortOceanContext,
) -> None:
    from azure_devops.client.auth import BearerAuthProvider
    from azure_devops.client.azure_devops_client import AzureDevopsClient

    client._organization_base_url = "https://dev.azure.com/org"
    client.webhook_auth_username = "hook-user"
    client.excluded_tags = ["tag1"]

    token_client = executor._client_for_token("oauth-token")

    assert isinstance(token_client, AzureDevopsClient)
    assert token_client._organization_base_url == "https://dev.azure.com/org"
    assert token_client.webhook_auth_username == "hook-user"
    assert token_client.excluded_tags == ["tag1"]
    assert isinstance(token_client._auth_provider, BearerAuthProvider)
