from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, AsyncIterator, Iterator, TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.config.settings import PortSettings

from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_text_block import (
    BetaManagedAgentsTextBlock,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_interrupt_event import (
    BetaManagedAgentsUserInterruptEvent,
)
from actions.abstract_executor import AbstractAnthropicExecutor
from actions.archive_agent_executor import (
    AGENT_ARCHIVED_STATUS_LABEL,
    ArchiveAgentExecutor,
)
from actions.cancel_session_executor import (
    SESSION_CANCELLED_STATUS_LABEL,
    SESSION_NOT_CANCELLABLE_STATUS_LABEL,
    CancelSessionExecutor,
)
from actions.create_agent_executor import (
    AGENT_CREATED_STATUS_LABEL,
    CreateAgentExecutor,
)
from actions.create_environment_executor import (
    ENVIRONMENT_CREATED_STATUS_LABEL,
    CreateEnvironmentExecutor,
)
from actions.delete_environment_executor import (
    ENVIRONMENT_DELETED_STATUS_LABEL,
    DeleteEnvironmentExecutor,
)
from actions.exceptions import InvalidActionParametersException
from actions.trigger_agent_executor import (
    PORT_IDENTITY_ID_KEY,
    SESSION_NOT_CONTINUABLE_STATUS_LABEL,
    TriggerAgentExecutor,
)
from actions.update_agent_executor import (
    AGENT_UPDATED_STATUS_LABEL,
    UpdateAgentExecutor,
)
from actions.update_environment_executor import (
    ENVIRONMENT_UPDATED_STATUS_LABEL,
    UpdateEnvironmentExecutor,
)
from actions.types import TriggerAgentSessionOutput, list_cost_to_usd
from actions.port_mcp_utils import (
    PORT_MCP_SERVER_NAME,
    PortMcpBinding,
    attach_port_mcp_settings_to_agent_config,
    ensure_port_mcp_binding,
)
from actions.utils import (
    build_external_id,
    build_session_link,
    normalize_session_config,
)
from anthropic.types.beta.beta_managed_agents_session_usage import (
    BetaManagedAgentsSessionUsage,
)
from clients.anthropic_client import RateLimitInfo
from port_ocean.core.models import ActionRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.tests.helpers.aes_gcm import encrypt_aes256_gcm

T = TypeVar("T", bound=AbstractAnthropicExecutor)

from tests.action_test_helpers import (
    build_executor,
    build_mock_ocean,
    mock_event_context,
    sdk_agent,
    update_agent_run,
)


@pytest.mark.asyncio
async def test_update_agent_executor_updates_and_completes() -> None:
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent(version=3))
    client_mock.update_agent = AsyncMock(return_value=sdk_agent(version=4))
    executor = build_executor(UpdateAgentExecutor, client_mock)

    run = update_agent_run()
    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    client_mock.get_agent.assert_awaited_once_with("agent_1")
    client_mock.update_agent.assert_awaited_once_with(
        "agent_1",
        version=3,
        payload={"name": "new-name"},
    )
    mock_ocean.register_raw.assert_awaited_once()
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run, True, "Updated agent agent_1", status_label=AGENT_UPDATED_STATUS_LABEL
    )


@pytest.mark.asyncio
async def test_update_agent_executor_sets_agent_id_output_for_workflow_nodes() -> None:
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent(version=1))
    client_mock.update_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(UpdateAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {"agentId": "agent_1", "name": "n"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    assert run.output == {"agentId": "agent_1"}


@pytest.mark.asyncio
async def test_update_agent_executor_skips_output_for_classic_action_runs() -> None:
    """Classic self-service action runs have no structured output field, so the
    executor must not touch `.output` on them (it doesn't exist on `ActionRun`)."""
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent(version=1))
    client_mock.update_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(UpdateAgentExecutor, client_mock)

    run = MagicMock(spec=ActionRun)
    run.id = "run_1"
    run.execution_properties = {"agentId": "agent_1", "name": "n"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    mock_ocean.port_client.report_run_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_agent_executor_requires_at_least_one_update_field() -> None:
    executor = build_executor(UpdateAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"agentId": "agent_1"}
    with pytest.raises(InvalidActionParametersException, match="at least one"):
        await executor.execute(run)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "properties",
    [{"enablePortMcp": False}, {"config": {}}],
)
async def test_update_agent_executor_rejects_updates_with_empty_payload(
    properties: dict[str, Any],
) -> None:
    executor = build_executor(UpdateAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"agentId": "agent_1", **properties}
    with pytest.raises(InvalidActionParametersException, match="at least one"):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_update_agent_executor_requires_agent_id() -> None:
    executor = build_executor(UpdateAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"name": "n"}
    with pytest.raises(InvalidActionParametersException):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_update_agent_executor_raises_on_get_agent_failure() -> None:
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(side_effect=RuntimeError("not found"))
    executor = build_executor(UpdateAgentExecutor, client_mock)

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        with pytest.raises(ActionExecutionError, match="not found"):
            await executor.execute(update_agent_run())

    client_mock.update_agent.assert_not_called()
    mock_ocean.register_raw.assert_not_awaited()
    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_agent_executor_raises_on_invalid_version() -> None:
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent(version=None))
    executor = build_executor(UpdateAgentExecutor, client_mock)

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        with pytest.raises(ActionExecutionError, match="unexpected version"):
            await executor.execute(update_agent_run())

    client_mock.update_agent.assert_not_called()
    mock_ocean.register_raw.assert_not_awaited()
    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_agent_executor_raises_on_update_failure() -> None:
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent(version=2))
    client_mock.update_agent = AsyncMock(side_effect=RuntimeError("conflict"))
    executor = build_executor(UpdateAgentExecutor, client_mock)

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        with pytest.raises(ActionExecutionError, match="conflict"):
            await executor.execute(update_agent_run())

    mock_ocean.register_raw.assert_not_awaited()
    mock_ocean.port_client.report_run_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_agent_executor_wires_port_mcp_when_flag_true() -> None:
    client_mock = MagicMock()
    current = sdk_agent(version=1, mcp_servers=[])
    current.tools = []
    client_mock.get_agent = AsyncMock(return_value=current)
    client_mock.update_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(UpdateAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "agentId": "agent_1",
        "enablePortMcp": True,
        "config": {"description": "d"},
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    payload = client_mock.update_agent.await_args.kwargs["payload"]
    assert payload["description"] == "d"
    assert "metadata" not in payload
    assert any(
        getattr(s, "name", None) == PORT_MCP_SERVER_NAME for s in payload["mcp_servers"]
    )
    assert "enablePortMcp" not in payload
    assert "config" not in payload


@pytest.mark.asyncio
async def test_update_agent_keeps_existing_tools_when_enabling_port_mcp() -> None:
    from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
        BetaManagedAgentsMCPServerURLDefinition,
    )

    existing_tool = MagicMock()
    existing_tool.type = "agent_toolset_20260401"
    existing_tool.name = "existing"
    current = sdk_agent(version=1)
    current.tools = [existing_tool]
    current.mcp_servers = [
        BetaManagedAgentsMCPServerURLDefinition(
            type="url", name="other", url="https://example.com"
        )
    ]
    current.metadata = {"keep": "yes"}
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=current)
    client_mock.update_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(UpdateAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {"agentId": "agent_1", "enablePortMcp": True}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    payload = client_mock.update_agent.await_args.kwargs["payload"]
    assert any(getattr(tool, "name", None) == "existing" for tool in payload["tools"])
    assert any(
        getattr(server, "name", None) == "other" for server in payload["mcp_servers"]
    )
    assert any(
        getattr(server, "name", None) == PORT_MCP_SERVER_NAME
        for server in payload["mcp_servers"]
    )


@pytest.mark.asyncio
async def test_update_agent_executor_maps_system_prompt_to_system_field() -> None:
    """systemPrompt in execution properties must arrive as `system` in the API payload."""
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent(version=1))
    client_mock.update_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(UpdateAgentExecutor, client_mock)

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.update_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(update_agent_run(name=None, systemPrompt="be helpful"))

    client_mock.update_agent.assert_awaited_once_with(
        "agent_1",
        version=1,
        payload={"system": "be helpful"},
    )


@pytest.mark.asyncio
async def test_update_agent_partition_key_is_agent_id() -> None:
    executor = build_executor(UpdateAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"agentId": "agent_1"}
    assert await executor._get_partition_key(run) == "agent_1"
