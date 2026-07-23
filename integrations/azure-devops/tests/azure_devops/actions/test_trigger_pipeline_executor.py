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
