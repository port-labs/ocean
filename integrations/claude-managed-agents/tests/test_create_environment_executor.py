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
    sdk_environment,
)


@pytest.mark.asyncio
async def test_create_environment_executor_creates_and_completes() -> None:
    client_mock = MagicMock()
    client_mock.create_environment = AsyncMock(return_value=sdk_environment())
    executor = build_executor(CreateEnvironmentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {"name": "my-env", "description": "test env"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_environment_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    client_mock.create_environment.assert_awaited_once_with(
        name="my-env", description="test env", scope=None, extra=None
    )
    mock_ocean.register_raw.assert_awaited_once()
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run,
        True,
        "Created environment env_1",
        status_label=ENVIRONMENT_CREATED_STATUS_LABEL,
    )


@pytest.mark.asyncio
async def test_create_environment_executor_sets_environment_id_output_for_workflow_nodes() -> (
    None
):
    client_mock = MagicMock()
    client_mock.create_environment = AsyncMock(return_value=sdk_environment())
    executor = build_executor(CreateEnvironmentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.output = {}
    run.execution_properties = {"name": "my-env"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_environment_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    assert run.output == {"environmentId": "env_1"}


@pytest.mark.asyncio
async def test_create_environment_executor_skips_output_for_classic_action_runs() -> (
    None
):
    """Classic self-service action runs have no structured output field, so the
    executor must not touch `.output` on them (it doesn't exist on `ActionRun`)."""
    client_mock = MagicMock()
    client_mock.create_environment = AsyncMock(return_value=sdk_environment())
    executor = build_executor(CreateEnvironmentExecutor, client_mock)

    run = MagicMock(spec=ActionRun)
    run.id = "run_1"
    run.execution_properties = {"name": "my-env"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_environment_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        await executor.execute(run)

    mock_ocean.port_client.report_run_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_environment_executor_reports_failure_on_api_error() -> None:
    client_mock = MagicMock()
    client_mock.create_environment = AsyncMock(
        side_effect=RuntimeError("quota exceeded")
    )
    executor = build_executor(CreateEnvironmentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {"name": "my-env"}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_environment_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", mock_event_context),
    ):
        with pytest.raises(ActionExecutionError, match="quota exceeded"):
            await executor.execute(run)

    mock_ocean.port_client.report_run_completed.assert_not_awaited()
    mock_ocean.register_raw.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_environment_executor_requires_name() -> None:
    executor = build_executor(CreateEnvironmentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {}
    with pytest.raises(InvalidActionParametersException):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_create_environment_executor_posts_warn_log_when_catalog_upsert_fails() -> (
    None
):
    """Catalog reflection is best-effort: a failure must not fail the run, but
    should surface as a warning run log in addition to the loguru warning."""
    client_mock = MagicMock()
    client_mock.create_environment = AsyncMock(return_value=sdk_environment())
    executor = build_executor(CreateEnvironmentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {"name": "my-env"}

    mock_ocean = build_mock_ocean()
    mock_ocean.register_raw = AsyncMock(side_effect=RuntimeError("catalog down"))
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_environment_executor.ocean", mock_ocean),
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
    assert "catalog down" in warn_calls[0].args[1]
    mock_ocean.port_client.report_run_completed.assert_awaited_once_with(
        run,
        True,
        "Created environment env_1",
        status_label=ENVIRONMENT_CREATED_STATUS_LABEL,
    )
