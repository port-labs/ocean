from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from actions.create_agent_executor import (
    AGENT_CREATED_STATUS_LABEL,
    CreateAgentExecutor,
)
from actions.exceptions import InvalidActionParametersException
from actions.port_mcp_utils import (
    PORT_MCP_SERVER_NAME,
)
from port_ocean.core.models import ActionRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError


from tests.action_test_helpers import (
    build_executor,
    build_mock_ocean,
    mock_event_context,
    sdk_agent,
)


@pytest.mark.asyncio
async def test_create_agent_executor_creates_and_completes() -> None:
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "name": "n",
        "model": "m",
        "systemPrompt": "s",
        "config": {"description": "d"},
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    extra = client_mock.create_agent.await_args.kwargs["extra"]
    assert extra["description"] == "d"
    assert any(
        getattr(s, "name", None) == PORT_MCP_SERVER_NAME for s in extra["mcp_servers"]
    )
    mock_ocean.register_raw.assert_awaited_once()
    mock_ocean.port_client.report_run_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_agent_executor_sets_agent_id_output_for_workflow_nodes() -> None:
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {"name": "n", "model": "m"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    assert run.output == {"agentId": "agent_1"}
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run, True, "Created agent agent_1", status_label=AGENT_CREATED_STATUS_LABEL
    )


@pytest.mark.asyncio
async def test_create_agent_executor_skips_output_for_classic_action_runs() -> None:
    """Classic self-service action runs have no structured output field, so the
    executor must not touch `.output` on them (it doesn't exist on `ActionRun`)."""
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock(spec=ActionRun)
    run.id = "run_1"
    run.execution_properties = {"name": "n", "model": "m"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run, True, "Created agent agent_1", status_label=AGENT_CREATED_STATUS_LABEL
    )


@pytest.mark.asyncio
async def test_create_agent_executor_posts_warn_log_when_catalog_upsert_fails() -> None:
    """Catalog reflection is best-effort: a failure must not fail the run, but
    should surface as a warning run log in addition to the loguru warning."""
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {"name": "n", "model": "m"}

    mock_ocean = build_mock_ocean()
    mock_ocean.register_raw = AsyncMock(side_effect=RuntimeError("port is down"))
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.port_client.post_run_log = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    warn_calls = [
        call
        for call in mock_ocean.port_client.post_run_log.await_args_list
        if call.kwargs.get("level") == "WARNING"
    ]
    assert len(warn_calls) == 1
    assert warn_calls[0].args[0] is run
    assert "port is down" in warn_calls[0].args[1]
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run, True, "Created agent agent_1", status_label=AGENT_CREATED_STATUS_LABEL
    )


@pytest.mark.asyncio
async def test_create_agent_executor_passes_config_through() -> None:
    """Config (including MCP servers declared by the workflow) is passed through unchanged."""
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(CreateAgentExecutor, client_mock)

    mcp_config = {
        "mcp_servers": [
            {
                "type": "url",
                "name": "port",
                "url": "https://mcp.getport.io/v1",
            }
        ],
        "tools": [
            {
                "type": "mcp_toolset",
                "mcp_server_name": "port",
                "default_config": {
                    "enabled": True,
                    "permission_policy": {"type": "always_allow"},
                },
            }
        ],
    }
    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "name": "n",
        "model": "claude-opus-4-8",
        "systemPrompt": "s",
        "config": mcp_config,
        "enablePortMcp": False,
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    client_mock.create_agent.assert_awaited_once_with(
        name="n",
        model="claude-opus-4-8",
        system="s",
        extra=mcp_config,
    )


@pytest.mark.asyncio
async def test_create_agent_executor_passes_skills_config_through() -> None:
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(CreateAgentExecutor, client_mock)

    skills = [{"type": "custom", "skill_id": "skill_01"}]
    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "name": "n",
        "model": "m",
        "systemPrompt": "s",
        "config": {"skills": skills},
        "enablePortMcp": False,
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    client_mock.create_agent.assert_awaited_once_with(
        name="n",
        model="m",
        system="s",
        extra={"skills": skills},
    )


@pytest.mark.asyncio
async def test_create_agent_executor_wires_port_mcp_when_flag_true() -> None:
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "name": "n",
        "model": "m",
        "enablePortMcp": True,
        "config": {"description": "d"},
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    extra = client_mock.create_agent.await_args.kwargs["extra"]
    assert extra["description"] == "d"
    assert "metadata" not in extra
    assert any(
        getattr(s, "name", None) == PORT_MCP_SERVER_NAME for s in extra["mcp_servers"]
    )


@pytest.mark.asyncio
async def test_create_agent_executor_skips_port_mcp_when_flag_false() -> None:
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "name": "n",
        "model": "m",
        "enablePortMcp": False,
        "config": {"description": "d"},
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    client_mock.create_agent.assert_awaited_once_with(
        name="n", model="m", system=None, extra={"description": "d"}
    )


@pytest.mark.asyncio
async def test_create_agent_executor_reports_failure_on_api_error() -> None:
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(side_effect=RuntimeError("quota exceeded"))
    executor = build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {"name": "n", "model": "m"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        with pytest.raises(ActionExecutionError, match="quota exceeded"):
            await executor.execute(run)

    mock_ocean.port_client.report_run_completed.assert_not_awaited()
    mock_ocean.register_raw.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_agent_executor_requires_name_and_model() -> None:
    executor = build_executor(CreateAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"name": "only-name"}
    with pytest.raises(InvalidActionParametersException):
        await executor.execute(run)
