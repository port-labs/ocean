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
    cancel_run,
    interrupt_event,
    mock_event_context,
    sdk_session,
)


@pytest.mark.asyncio
async def test_cancel_session_requires_session_id() -> None:
    executor = build_executor(CancelSessionExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {}

    with pytest.raises(InvalidActionParametersException, match="sessionId"):
        await executor.execute(run)


@pytest.mark.asyncio
@pytest.mark.parametrize("session_id", ["", 123])
async def test_cancel_session_rejects_invalid_session_id(session_id: Any) -> None:
    client_mock = MagicMock()
    client_mock.get_session = AsyncMock()
    executor = build_executor(CancelSessionExecutor, client_mock)

    with pytest.raises(InvalidActionParametersException, match="sessionId"):
        await executor.execute(cancel_run(sessionId=session_id))

    client_mock.get_session.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_session_partition_key_is_session_id() -> None:
    executor = build_executor(CancelSessionExecutor, MagicMock())
    assert await executor._get_partition_key(cancel_run()) == "sess_1"


@pytest.mark.asyncio
async def test_cancel_session_partition_key_is_none_without_session_id() -> None:
    executor = build_executor(CancelSessionExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {}
    assert await executor._get_partition_key(run) is None


@pytest.mark.asyncio
async def test_cancel_session_interrupts_running_session() -> None:
    client_mock = MagicMock()
    client_mock.get_session = AsyncMock(return_value=sdk_session(status="running"))
    client_mock.send_user_interrupt = AsyncMock(return_value=interrupt_event())
    executor = build_executor(CancelSessionExecutor, client_mock)

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    run = cancel_run()
    with (
        patch("actions.cancel_session_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    client_mock.send_user_interrupt.assert_awaited_once_with("sess_1", None)
    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert mock_ocean.port_client.report_run_completed.call_args.args[1] is True
    assert (
        mock_ocean.port_client.report_run_completed.call_args.kwargs["status_label"]
        == SESSION_CANCELLED_STATUS_LABEL
    )


@pytest.mark.asyncio
async def test_cancel_session_forwards_session_thread_id() -> None:
    client_mock = MagicMock()
    client_mock.get_session = AsyncMock(return_value=sdk_session(status="running"))
    client_mock.send_user_interrupt = AsyncMock(return_value=interrupt_event())
    executor = build_executor(CancelSessionExecutor, client_mock)

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.cancel_session_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(cancel_run(sessionThreadId="thr_1"))

    client_mock.send_user_interrupt.assert_awaited_once_with("sess_1", "thr_1")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["idle", "terminated", "rescheduled"])
async def test_cancel_session_rejects_non_running_session(status: str) -> None:
    client_mock = MagicMock()
    client_mock.get_session = AsyncMock(return_value=sdk_session(status=status))
    client_mock.send_user_interrupt = AsyncMock()
    executor = build_executor(CancelSessionExecutor, client_mock)

    mock_ocean = build_mock_ocean()
    with (
        patch("actions.cancel_session_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
    ):
        with pytest.raises(ActionExecutionError) as exc_info:
            await executor.execute(cancel_run())

    assert exc_info.value.status_label == SESSION_NOT_CANCELLABLE_STATUS_LABEL
    client_mock.send_user_interrupt.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_session_wraps_upstream_failure() -> None:
    client_mock = MagicMock()
    client_mock.get_session = AsyncMock(return_value=sdk_session(status="running"))
    client_mock.send_user_interrupt = AsyncMock(side_effect=RuntimeError("boom"))
    executor = build_executor(CancelSessionExecutor, client_mock)

    mock_ocean = build_mock_ocean()
    with (
        patch("actions.cancel_session_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
    ):
        with pytest.raises(ActionExecutionError, match="boom"):
            await executor.execute(cancel_run())


@pytest.mark.asyncio
async def test_cancel_session_sets_workflow_node_outputs() -> None:
    client_mock = MagicMock()
    client_mock.get_session = AsyncMock(return_value=sdk_session(status="running"))
    client_mock.send_user_interrupt = AsyncMock(return_value=interrupt_event("int_9"))
    executor = build_executor(CancelSessionExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.execution_properties = {"sessionId": "sess_1"}
    run.output = {}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.cancel_session_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    assert run.output == {"sessionId": "sess_1", "interruptEventId": "int_9"}
