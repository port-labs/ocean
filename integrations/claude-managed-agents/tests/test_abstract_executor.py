from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from actions.create_agent_executor import (
    CreateAgentExecutor,
)
from actions.trigger_agent_executor import (
    TriggerAgentExecutor,
)
from clients.anthropic_client import RateLimitInfo


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
