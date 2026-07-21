from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

import core.webhook_signing as webhook_signing
from actions.abstract_executor import AbstractCursorExecutor
from actions.create_agent_executor import CreateAgentExecutor
from actions.exceptions import InvalidActionParametersException
from actions.trigger_agent_executor import TriggerAgentExecutor

T = TypeVar("T", bound=AbstractCursorExecutor)

_V0_LAUNCH_AGENT: dict[str, object] = {
    "id": "bc-1",
    "status": "CREATING",
    "source": {"repository": "https://github.com/org/repo", "ref": "main"},
    "target": {"url": "https://cursor.com/agents?id=bc-1"},
    "createdAt": "2026-07-16T11:11:03.025Z",
}


@pytest.fixture(autouse=True)
def _reset_org_id_cache() -> None:
    webhook_signing._org_id_cache = None


@asynccontextmanager
async def _noop_event_context(*args: Any, **kwargs: Any) -> AsyncIterator[None]:
    yield


def _build_executor(executor_cls: type[T], client_mock: MagicMock) -> T:
    with patch(
        "actions.abstract_executor.create_cursor_agents_client",
        return_value=client_mock,
    ):
        return executor_cls()


def _build_mock_ocean(*, base_url: str | None = "https://cca.example.com") -> MagicMock:
    mock_ocean = MagicMock()
    mock_ocean.app.base_url = base_url
    mock_ocean.config.port.client_secret = "test-port-client-secret"
    mock_ocean.port_client.get_org_id = AsyncMock(return_value="test-org-id")
    mock_ocean.register_raw = AsyncMock()
    mock_ocean.integration.port_app_config_handler.get_port_app_config = AsyncMock()
    return mock_ocean


def _patch_common(mock_ocean: MagicMock, *executor_modules: str) -> list[Any]:
    patches: list[Any] = [patch(module, mock_ocean) for module in executor_modules]
    patches.append(patch("actions.abstract_executor.ocean", mock_ocean))
    patches.append(patch("actions.utils.ocean", mock_ocean))
    patches.append(patch("core.webhook_signing.ocean", mock_ocean))
    patches.append(patch("core.catalog.ocean", mock_ocean))
    patches.append(patch("core.catalog.event_context", _noop_event_context))
    return patches


def _apply(patches: list[Any]) -> None:
    for p in patches:
        p.start()


def _stop(patches: list[Any]) -> None:
    for p in patches:
        p.stop()


@pytest.mark.asyncio
async def test_create_agent_executor_uses_v1_by_default() -> None:
    client_mock = MagicMock()
    client_mock.send_api_request = AsyncMock(
        return_value={
            "agent": {"id": "bc-1", "url": "https://cursor.com/agents/bc-1"},
            "run": {"id": "run-1"},
        }
    )
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "prompt": "Add a README",
        "repository": "https://github.com/org/repo",
        "apiVersion": "v1",
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    client_mock.send_api_request.assert_awaited_once()
    assert client_mock.send_api_request.await_args is not None
    assert client_mock.send_api_request.await_args.args[0] == "POST"
    assert client_mock.send_api_request.await_args.args[1] == "/v1/agents"
    assert run.output["agentId"] == "bc-1"
    assert run.output["runId"] == "run-1"
    assert mock_ocean.register_raw.await_count == 2
    mock_ocean.register_raw.assert_any_await(
        "agent", [{"id": "bc-1", "url": "https://cursor.com/agents/bc-1"}]
    )
    mock_ocean.register_raw.assert_any_await(
        "run", [{"id": "run-1", "agentId": "bc-1"}]
    )
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run, True, "Created agent bc-1"
    )


@pytest.mark.asyncio
async def test_create_agent_executor_rejects_report_completion_on_v1() -> None:
    executor = _build_executor(CreateAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {
        "prompt": "Add a README",
        "repository": "https://github.com/org/repo",
        "apiVersion": "v1",
        "reportCompletion": True,
    }
    with pytest.raises(
        InvalidActionParametersException,
        match="only supported on create_agent with apiVersion v0",
    ):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_create_agent_executor_v0_tracked_with_webhook() -> None:
    client_mock = MagicMock()
    client_mock.get_console_host.return_value = "https://cursor.com"
    client_mock.send_api_request = AsyncMock(return_value=_V0_LAUNCH_AGENT)
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "prompt": "Add a README",
        "repository": "https://github.com/org/repo",
        "apiVersion": "v0",
        "reportCompletion": True,
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    patches.append(
        patch(
            "actions.create_agent_executor.list_first_runs_page",
            AsyncMock(return_value=[{"id": "run-1", "status": "CREATING"}]),
        )
    )
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    client_mock.send_api_request.assert_awaited_once()
    assert client_mock.send_api_request.await_args is not None
    assert client_mock.send_api_request.await_args.args == (
        "POST",
        "/v0/agents",
    )
    assert run.output["agentId"] == "bc-1"
    assert mock_ocean.register_raw.await_count == 2
    mock_ocean.register_raw.assert_any_await(
        "agent",
        [
            {
                "id": "bc-1",
                "status": "ACTIVE",
                "source": _V0_LAUNCH_AGENT["source"],
                "target": _V0_LAUNCH_AGENT["target"],
                "repos": [{"url": "https://github.com/org/repo"}],
                "url": "https://cursor.com/agents?id=bc-1",
                "createdAt": "2026-07-16T11:11:03.025Z",
            }
        ],
    )
    mock_ocean.register_raw.assert_any_await(
        "run",
        [{"id": "run-1", "status": "CREATING", "agentId": "bc-1"}],
    )
    mock_ocean.port_client.update_run_started.assert_awaited_once()
    assert mock_ocean.port_client.update_run_started.call_args.args[2] == "bc-1"

    launch_body = client_mock.send_api_request.await_args.kwargs["json_body"]
    assert launch_body["webhook"]["url"] == (
        "https://cca.example.com/integration/webhook/run_1"
    )
    assert len(launch_body["webhook"]["secret"]) >= 32


@pytest.mark.asyncio
async def test_create_agent_executor_v0_without_tracking_completes_immediately() -> (
    None
):
    client_mock = MagicMock()
    client_mock.get_console_host.return_value = "https://cursor.com"
    client_mock.send_api_request = AsyncMock(return_value=_V0_LAUNCH_AGENT)
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "prompt": "Add a README",
        "repository": "https://github.com/org/repo",
        "apiVersion": "v0",
        "reportCompletion": False,
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    patches.append(
        patch(
            "actions.create_agent_executor.list_first_runs_page",
            AsyncMock(return_value=[{"id": "run-1", "status": "CREATING"}]),
        )
    )
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    launch_body = client_mock.send_api_request.await_args.kwargs["json_body"]
    assert "webhook" not in launch_body
    assert mock_ocean.register_raw.await_count == 2
    mock_ocean.register_raw.assert_any_await(
        "agent",
        [
            {
                "id": "bc-1",
                "status": "ACTIVE",
                "source": _V0_LAUNCH_AGENT["source"],
                "target": _V0_LAUNCH_AGENT["target"],
                "repos": [{"url": "https://github.com/org/repo"}],
                "url": "https://cursor.com/agents?id=bc-1",
                "createdAt": "2026-07-16T11:11:03.025Z",
            }
        ],
    )
    mock_ocean.register_raw.assert_any_await(
        "run",
        [{"id": "run-1", "status": "CREATING", "agentId": "bc-1"}],
    )
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run, True, "Launched agent bc-1"
    )


@pytest.mark.asyncio
async def test_create_agent_executor_v0_tracked_requires_base_url() -> None:
    executor = _build_executor(CreateAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {
        "prompt": "Add a README",
        "repository": "https://github.com/org/repo",
        "apiVersion": "v0",
        "reportCompletion": True,
    }

    mock_ocean = _build_mock_ocean(base_url=None)
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    _apply(patches)
    try:
        with pytest.raises(
            InvalidActionParametersException, match="reachable public URL"
        ):
            await executor.execute(run)
    finally:
        _stop(patches)


@pytest.mark.asyncio
async def test_create_agent_executor_allows_v1_config_on_v0() -> None:
    client_mock = MagicMock()
    client_mock.get_console_host.return_value = "https://cursor.com"
    client_mock.send_api_request = AsyncMock(return_value=_V0_LAUNCH_AGENT)
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "prompt": "Add a README",
        "repository": "https://github.com/org/repo",
        "apiVersion": "v0",
        "config": {"mcpServers": []},
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    patches.append(
        patch(
            "actions.create_agent_executor.list_first_runs_page",
            AsyncMock(return_value=[]),
        )
    )
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    launch_body = client_mock.send_api_request.await_args.kwargs["json_body"]
    assert launch_body["mcpServers"] == []


@pytest.mark.asyncio
async def test_create_agent_executor_requires_prompt_in_merged_body() -> None:
    executor = _build_executor(CreateAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"repository": "https://github.com/org/repo"}
    with pytest.raises(InvalidActionParametersException, match="prompt"):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_create_agent_executor_allows_prompt_in_config_only() -> None:
    client_mock = MagicMock()
    client_mock.send_api_request = AsyncMock(
        return_value={
            "agent": {"id": "bc-1", "url": "https://cursor.com/agents/bc-1"},
            "run": {"id": "run-1"},
        }
    )
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "repository": "https://github.com/org/repo",
        "config": {"prompt": {"text": "from config"}},
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    client_mock.send_api_request.assert_awaited_once_with(
        "POST",
        "/v1/agents",
        json_body={
            "repos": [{"url": "https://github.com/org/repo"}],
            "prompt": {"text": "from config"},
        },
    )


@pytest.mark.asyncio
async def test_create_agent_executor_v0_allows_missing_source() -> None:
    client_mock = MagicMock()
    client_mock.get_console_host.return_value = "https://cursor.com"
    client_mock.send_api_request = AsyncMock(return_value=_V0_LAUNCH_AGENT)
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {"prompt": "go", "apiVersion": "v0"}

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    patches.append(
        patch(
            "actions.create_agent_executor.list_first_runs_page",
            AsyncMock(return_value=[]),
        )
    )
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    launch_body = client_mock.send_api_request.await_args.kwargs["json_body"]
    assert launch_body["source"] == {}


@pytest.mark.asyncio
async def test_create_agent_executor_v0_uses_model_id_string_from_config() -> None:
    client_mock = MagicMock()
    client_mock.get_console_host.return_value = "https://cursor.com"
    client_mock.send_api_request = AsyncMock(return_value=_V0_LAUNCH_AGENT)
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "prompt": "Add a README",
        "repository": "https://github.com/org/repo",
        "apiVersion": "v0",
        "config": {"model": "composer-2.5"},
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    patches.append(
        patch(
            "actions.create_agent_executor.list_first_runs_page",
            AsyncMock(return_value=[]),
        )
    )
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    launch_body = client_mock.send_api_request.await_args.kwargs["json_body"]
    assert launch_body["model"] == "composer-2.5"
    assert "model" not in launch_body.get("target", {})


@pytest.mark.asyncio
async def test_create_agent_executor_v0_uses_model_object_from_config() -> None:
    client_mock = MagicMock()
    client_mock.get_console_host.return_value = "https://cursor.com"
    client_mock.send_api_request = AsyncMock(return_value=_V0_LAUNCH_AGENT)
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "prompt": "Add a README",
        "repository": "https://github.com/org/repo",
        "apiVersion": "v0",
        "config": {
            "model": {
                "id": "composer-2.5",
                "params": [{"id": "fast", "value": "false"}],
            }
        },
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    patches.append(
        patch(
            "actions.create_agent_executor.list_first_runs_page",
            AsyncMock(return_value=[]),
        )
    )
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    launch_body = client_mock.send_api_request.await_args.kwargs["json_body"]
    assert launch_body["model"] == "composer-2.5"
    assert "model" not in launch_body.get("target", {})


@pytest.mark.asyncio
async def test_create_agent_executor_v0_uses_webhook_from_config() -> None:
    client_mock = MagicMock()
    client_mock.get_console_host.return_value = "https://cursor.com"
    client_mock.send_api_request = AsyncMock(return_value=_V0_LAUNCH_AGENT)
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "prompt": "Add a README",
        "repository": "https://github.com/org/repo",
        "apiVersion": "v0",
        "reportCompletion": False,
        "config": {
            "webhook": {
                "url": "https://example.com/custom-hook",
                "secret": "s" * 32,
            }
        },
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    patches.append(
        patch(
            "actions.create_agent_executor.list_first_runs_page",
            AsyncMock(return_value=[]),
        )
    )
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    launch_body = client_mock.send_api_request.await_args.kwargs["json_body"]
    assert launch_body["webhook"] == {
        "url": "https://example.com/custom-hook",
        "secret": "s" * 32,
    }
    assert "webhook" not in launch_body.get("target", {})


@pytest.mark.asyncio
async def test_create_agent_executor_v0_rejects_webhook_with_report_completion() -> (
    None
):
    executor = _build_executor(CreateAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {
        "prompt": "Add a README",
        "repository": "https://github.com/org/repo",
        "apiVersion": "v0",
        "reportCompletion": True,
        "config": {
            "webhook": {
                "url": "https://example.com/custom-hook",
                "secret": "s" * 32,
            }
        },
    }
    with pytest.raises(
        InvalidActionParametersException,
        match="config.webhook cannot be set when reportCompletion is true",
    ):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_create_agent_executor_v1_requires_workspace() -> None:
    executor = _build_executor(CreateAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"prompt": "go", "apiVersion": "v1"}
    with pytest.raises(InvalidActionParametersException, match="requires a workspace"):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_create_agent_executor_v1_requires_workspace_for_pr_url_only() -> None:
    executor = _build_executor(CreateAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {
        "prompt": "go",
        "apiVersion": "v1",
        "prUrl": "https://github.com/org/repo/pull/1",
    }
    with pytest.raises(InvalidActionParametersException, match="requires a workspace"):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_create_agent_executor_v1_allows_env_config_without_repository() -> None:
    client_mock = MagicMock()
    client_mock.send_api_request = AsyncMock(
        return_value={
            "agent": {"id": "bc-1", "url": "https://cursor.com/agents/bc-1"},
            "run": {"id": "run-1"},
        }
    )
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "prompt": "go",
        "apiVersion": "v1",
        "config": {"env": {"type": "cloud", "name": "my-env"}},
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    client_mock.send_api_request.assert_awaited_once_with(
        "POST",
        "/v1/agents",
        json_body={
            "prompt": {"text": "go"},
            "env": {"type": "cloud", "name": "my-env"},
        },
    )


@pytest.mark.asyncio
async def test_create_agent_executor_reports_cursor_api_error_on_v1_failure() -> None:
    client_mock = MagicMock()
    request = httpx.Request("POST", "https://api.cursor.com/v1/agents")
    response = httpx.Response(
        400,
        text=(
            '{"error":{"code":"invalid_model","message":"Model \'composer-2.5\' '
            'does not match a known variant."}}'
        ),
        request=request,
    )
    client_mock.send_api_request = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            (
                "HTTP 400 for POST https://api.cursor.com/v1/agents: "
                '{"error":{"code":"invalid_model","message":"Model \'composer-2.5\' '
                'does not match a known variant."}}'
            ),
            request=request,
            response=response,
        )
    )
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "prompt": "go",
        "repository": "https://github.com/org/repo",
        "apiVersion": "v1",
        "model": {"id": "composer-2.5"},
    }

    mock_ocean = _build_mock_ocean()
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    _apply(patches)
    try:
        with pytest.raises(ActionExecutionError, match="invalid_model.*composer-2.5"):
            await executor.execute(run)
    finally:
        _stop(patches)


@pytest.mark.asyncio
async def test_create_agent_executor_reports_failure_on_v1_error() -> None:
    client_mock = MagicMock()
    client_mock.send_api_request = AsyncMock(side_effect=RuntimeError("boom"))
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "prompt": "go",
        "repository": "https://github.com/org/repo",
        "apiVersion": "v1",
    }

    mock_ocean = _build_mock_ocean()
    patches = _patch_common(mock_ocean, "actions.create_agent_executor.ocean")
    _apply(patches)
    try:
        with pytest.raises(ActionExecutionError, match="boom"):
            await executor.execute(run)
    finally:
        _stop(patches)


@pytest.mark.asyncio
async def test_trigger_agent_executor_uses_v1_by_default() -> None:
    client_mock = MagicMock()
    client_mock.send_api_request = AsyncMock(return_value={"run": {"id": "run-2"}})
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {"agentId": "bc-1", "prompt": "follow up"}

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.trigger_agent_executor.ocean")
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    client_mock.send_api_request.assert_awaited_once_with(
        "POST",
        "/v1/agents/bc-1/runs",
        json_body={"prompt": {"text": "follow up"}},
    )
    mock_ocean.register_raw.assert_awaited_once_with(
        "run", [{"id": "run-2", "agentId": "bc-1"}]
    )
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run, True, "Follow-up sent to agent bc-1"
    )


@pytest.mark.asyncio
async def test_trigger_agent_executor_tracked_agent_uses_v1_then_waits_for_webhook() -> (
    None
):
    client_mock = MagicMock()
    client_mock.get_console_host.return_value = "https://cursor.com"
    client_mock.send_api_request = AsyncMock(
        return_value={"run": {"id": "run-2", "agentId": "bc-1"}}
    )
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "agentId": "bc-1",
        "prompt": "follow up",
        "reportCompletion": True,
        "config": {"mode": "plan"},
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=MagicMock())
    patches = _patch_common(mock_ocean, "actions.trigger_agent_executor.ocean")
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    client_mock.send_api_request.assert_awaited_once_with(
        "POST",
        "/v1/agents/bc-1/runs",
        json_body={"prompt": {"text": "follow up"}, "mode": "plan"},
    )
    mock_ocean.register_raw.assert_awaited_once_with(
        "run", [{"id": "run-2", "agentId": "bc-1"}]
    )
    mock_ocean.port_client.update_run_started.assert_awaited_once()
    assert mock_ocean.port_client.update_run_started.call_args.args[2] == "run-2"


@pytest.mark.asyncio
async def test_trigger_agent_executor_untracked_agent_completes_immediately() -> None:
    client_mock = MagicMock()
    client_mock.send_api_request = AsyncMock(return_value={"run": {"id": "run-2"}})
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "agentId": "bc-1",
        "prompt": "follow up",
        "reportCompletion": True,
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.port_client.find_run_by_external_id = AsyncMock(return_value=None)
    patches = _patch_common(mock_ocean, "actions.trigger_agent_executor.ocean")
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    client_mock.send_api_request.assert_awaited_once()
    mock_ocean.register_raw.assert_awaited_once_with(
        "run", [{"id": "run-2", "agentId": "bc-1"}]
    )
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run, True, "Follow-up sent to agent bc-1"
    )


@pytest.mark.asyncio
async def test_trigger_agent_executor_requires_prompt_in_merged_body() -> None:
    executor = _build_executor(TriggerAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"agentId": "bc-1"}
    with pytest.raises(InvalidActionParametersException, match="prompt"):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_trigger_agent_executor_allows_prompt_in_config_only() -> None:
    client_mock = MagicMock()
    client_mock.send_api_request = AsyncMock(return_value={"run": {"id": "run-2"}})
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "agentId": "bc-1",
        "config": {"prompt": {"text": "follow up from config"}},
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.trigger_agent_executor.ocean")
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    client_mock.send_api_request.assert_awaited_once_with(
        "POST",
        "/v1/agents/bc-1/runs",
        json_body={"prompt": {"text": "follow up from config"}},
    )


@pytest.mark.asyncio
async def test_trigger_agent_partition_key_is_agent_id() -> None:
    executor = _build_executor(TriggerAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"agentId": "bc-1"}
    assert await executor._get_partition_key(run) == "bc-1"


@pytest.mark.asyncio
async def test_trigger_agent_executor_rejects_non_dict_config() -> None:
    executor = _build_executor(TriggerAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {
        "agentId": "bc-1",
        "prompt": "go",
        "config": "nope",
    }
    with pytest.raises(
        InvalidActionParametersException, match="config must be an object"
    ):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_trigger_agent_executor_allows_unknown_config_keys() -> None:
    client_mock = MagicMock()
    client_mock.send_api_request = AsyncMock(return_value={"run": {"id": "run-2"}})
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {
        "agentId": "bc-1",
        "prompt": "go",
        "config": {"envVars": {"X": "y"}},
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    patches = _patch_common(mock_ocean, "actions.trigger_agent_executor.ocean")
    _apply(patches)
    try:
        await executor.execute(run)
    finally:
        _stop(patches)

    client_mock.send_api_request.assert_awaited_once_with(
        "POST",
        "/v1/agents/bc-1/runs",
        json_body={"prompt": {"text": "go"}, "envVars": {"X": "y"}},
    )


@pytest.mark.asyncio
async def test_abstract_executor_is_never_close_to_rate_limit() -> None:
    executor = _build_executor(CreateAgentExecutor, MagicMock())
    assert await executor.is_close_to_rate_limit() is False
    assert await executor.get_remaining_seconds_until_rate_limit() == 0.0


@pytest.mark.asyncio
async def test_register_entity_posts_warn_log_on_catalog_failure() -> None:
    executor = _build_executor(CreateAgentExecutor, MagicMock())
    mock_ocean = _build_mock_ocean()
    mock_ocean.register_raw = AsyncMock(side_effect=RuntimeError("port is down"))
    mock_ocean.port_client.post_run_log = AsyncMock()

    run = MagicMock()
    run.id = "run_1"

    patches = [
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("core.catalog.ocean", mock_ocean),
        patch("core.catalog.event_context", _noop_event_context),
    ]
    _apply(patches)
    try:
        await executor.register_entity("agent", {"id": "bc-1"}, run)
    finally:
        _stop(patches)

    mock_ocean.port_client.post_run_log.assert_awaited_once()
    call = mock_ocean.port_client.post_run_log.call_args
    assert call.args[0] is run
    assert "port is down" in call.args[1]
    assert call.kwargs["level"] == "WARNING"
