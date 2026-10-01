"""Tests for AbstractGithubExecutor rate limit checking."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github.actions.abstract_github_executor import (
    MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS,
    AbstractGithubExecutor,
)
from github.clients.rate_limiter.utils import RateLimitInfo
from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.models import IntegrationRun


class StubGithubExecutor(AbstractGithubExecutor):
    ACTION_NAME = "stub"

    async def execute(self, run: IntegrationRun) -> None:
        pass


def make_client(remaining: int, seconds_until_reset: float) -> MagicMock:
    client = MagicMock(spec=GithubRestClient)
    client.get_rate_limit_status.return_value = RateLimitInfo(
        remaining=remaining,
        limit=5000,
        reset_time=int(time.time()) + int(seconds_until_reset),
    )
    return client


def make_run() -> MagicMock:
    run = MagicMock(spec=IntegrationRun)
    run.execution_properties = {"org": "test-org"}
    return run


class TestAbstractGithubExecutorRateLimits:
    @pytest.mark.asyncio
    async def test_is_close_to_rate_limit_returns_true_when_below_threshold(
        self,
    ) -> None:
        client = make_client(MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS - 1, 30)
        executor = StubGithubExecutor()
        run = make_run()

        with patch(
            "github.actions.abstract_github_executor.create_github_client_for_org",
            new=AsyncMock(return_value=client),
        ):
            assert await executor.is_close_to_rate_limit(run) is True

    @pytest.mark.asyncio
    async def test_is_close_to_rate_limit_returns_false_when_above_threshold(
        self,
    ) -> None:
        client = make_client(MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS, 30)
        executor = StubGithubExecutor()
        run = make_run()

        with patch(
            "github.actions.abstract_github_executor.create_github_client_for_org",
            new=AsyncMock(return_value=client),
        ):
            assert await executor.is_close_to_rate_limit(run) is False

    @pytest.mark.asyncio
    async def test_is_close_to_rate_limit_returns_false_when_no_rate_info(
        self,
    ) -> None:
        client = MagicMock(spec=GithubRestClient)
        client.get_rate_limit_status.return_value = None
        executor = StubGithubExecutor()
        run = make_run()

        with patch(
            "github.actions.abstract_github_executor.create_github_client_for_org",
            new=AsyncMock(return_value=client),
        ):
            assert await executor.is_close_to_rate_limit(run) is False

    @pytest.mark.asyncio
    async def test_get_remaining_seconds_returns_seconds_until_reset(
        self,
    ) -> None:
        client = make_client(100, 42.0)
        executor = StubGithubExecutor()
        run = make_run()

        with patch(
            "github.actions.abstract_github_executor.create_github_client_for_org",
            new=AsyncMock(return_value=client),
        ):
            assert await executor.get_remaining_seconds_until_rate_limit(run) == 42.0

    @pytest.mark.asyncio
    async def test_get_remaining_seconds_returns_zero_when_no_rate_info(
        self,
    ) -> None:
        client = MagicMock(spec=GithubRestClient)
        client.get_rate_limit_status.return_value = None
        executor = StubGithubExecutor()
        run = make_run()

        with patch(
            "github.actions.abstract_github_executor.create_github_client_for_org",
            new=AsyncMock(return_value=client),
        ):
            assert await executor.get_remaining_seconds_until_rate_limit(run) == 0.0
