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
    rate_limit_client_mock,
)

@pytest.mark.asyncio
async def test_is_close_to_rate_limit_false_when_no_status_cached() -> None:
    client_mock = rate_limit_client_mock()
    executor = build_executor(CreateAgentExecutor, client_mock)

    assert await executor.is_close_to_rate_limit(MagicMock()) is False

@pytest.mark.asyncio
async def test_is_close_to_rate_limit_false_with_healthy_headroom() -> None:
    client_mock = rate_limit_client_mock(
        create=RateLimitInfo(
            limit=300,
            remaining=250,
            reset=datetime.now(timezone.utc) + timedelta(seconds=30),
        ),
        read=RateLimitInfo(
            limit=1200,
            remaining=1000,
            reset=datetime.now(timezone.utc) + timedelta(seconds=30),
        ),
    )
    executor = build_executor(CreateAgentExecutor, client_mock)

    assert await executor.is_close_to_rate_limit(MagicMock()) is False

@pytest.mark.asyncio
async def test_is_close_to_rate_limit_true_when_create_pool_nearly_exhausted() -> None:
    client_mock = rate_limit_client_mock(
        create=RateLimitInfo(
            limit=300,
            remaining=20,
            reset=datetime.now(timezone.utc) + timedelta(seconds=30),
        )
    )
    executor = build_executor(CreateAgentExecutor, client_mock)

    assert await executor.is_close_to_rate_limit(MagicMock()) is True

@pytest.mark.asyncio
async def test_is_close_to_rate_limit_true_when_read_pool_nearly_exhausted() -> None:
    """`TriggerAgentExecutor._ensure_session_continuable` makes only read
    calls before ever reaching a create/send call, so a run should be
    deferred if the read pool alone is close to exhausted."""

    client_mock = rate_limit_client_mock(
        create=RateLimitInfo(
            limit=300,
            remaining=250,
            reset=datetime.now(timezone.utc) + timedelta(seconds=30),
        ),
        read=RateLimitInfo(
            limit=1200,
            remaining=50,
            reset=datetime.now(timezone.utc) + timedelta(seconds=30),
        ),
    )
    executor = build_executor(TriggerAgentExecutor, client_mock)

    assert await executor.is_close_to_rate_limit(MagicMock()) is True

@pytest.mark.asyncio
async def test_get_remaining_seconds_until_rate_limit_zero_when_no_status_cached() -> (
    None
):
    client_mock = rate_limit_client_mock()
    executor = build_executor(CreateAgentExecutor, client_mock)

    assert await executor.get_remaining_seconds_until_rate_limit(MagicMock()) == 0.0

@pytest.mark.asyncio
async def test_get_remaining_seconds_until_rate_limit_matches_reset_window() -> None:
    reset_at = datetime.now(timezone.utc) + timedelta(seconds=42)
    client_mock = rate_limit_client_mock(
        create=RateLimitInfo(limit=300, remaining=1, reset=reset_at)
    )
    executor = build_executor(CreateAgentExecutor, client_mock)

    remaining = await executor.get_remaining_seconds_until_rate_limit(MagicMock())
    assert 40 <= remaining <= 42

@pytest.mark.asyncio
async def test_get_remaining_seconds_until_rate_limit_waits_for_slower_pool() -> None:
    """When both pools are close to exhausted, wait for whichever one clears
    last so the execution manager doesn't retry too early."""

    client_mock = rate_limit_client_mock(
        create=RateLimitInfo(
            limit=300,
            remaining=1,
            reset=datetime.now(timezone.utc) + timedelta(seconds=10),
        ),
        read=RateLimitInfo(
            limit=1200,
            remaining=1,
            reset=datetime.now(timezone.utc) + timedelta(seconds=42),
        ),
    )
    executor = build_executor(TriggerAgentExecutor, client_mock)

    remaining = await executor.get_remaining_seconds_until_rate_limit(MagicMock())
    assert 40 <= remaining <= 42

@pytest.mark.asyncio
async def test_get_remaining_seconds_until_rate_limit_ignores_healthy_pool() -> None:
    """A pool with plenty of headroom shouldn't extend the wait time even if
    it happens to reset later than the exhausted pool."""

    reset_at = datetime.now(timezone.utc) + timedelta(seconds=10)
    client_mock = rate_limit_client_mock(
        create=RateLimitInfo(limit=300, remaining=1, reset=reset_at),
        read=RateLimitInfo(
            limit=1200,
            remaining=1000,
            reset=datetime.now(timezone.utc) + timedelta(seconds=999),
        ),
    )
    executor = build_executor(TriggerAgentExecutor, client_mock)

    remaining = await executor.get_remaining_seconds_until_rate_limit(MagicMock())
    assert 8 <= remaining <= 10

@pytest.mark.asyncio
async def test_is_close_to_rate_limit_false_once_reset_time_has_passed() -> None:
    """A stale cache past its reset must not wedge the execution manager's
    backoff loop forever: nothing refreshes the cache while backing off, so a
    passed reset has to be treated as fully replenished."""

    stale_reset = datetime.now(timezone.utc) - timedelta(seconds=5)
    client_mock = rate_limit_client_mock(
        create=RateLimitInfo(limit=300, remaining=1, reset=stale_reset)
    )
    executor = build_executor(CreateAgentExecutor, client_mock)

    assert await executor.is_close_to_rate_limit(MagicMock()) is False
