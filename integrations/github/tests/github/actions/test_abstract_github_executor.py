"""Tests for AbstractGithubExecutor rate limit aggregation."""

import time
from unittest.mock import MagicMock

import pytest

from github.actions.abstract_github_executor import (
    MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW,
    AbstractGithubExecutor,
)
from github.clients.rate_limiter.utils import RateLimitInfo
from github.clients.http.base_client import AbstractGithubClient
from port_ocean.core.models import IntegrationRun


class StubGithubExecutor(AbstractGithubExecutor):
    ACTION_NAME = "stub"
    WEBHOOK_PROCESSOR_CLASS = None

    def __init__(self, clients: list[AbstractGithubClient]) -> None:
        self._clients = clients

    async def _get_execution_clients(
        self, run: IntegrationRun
    ) -> list[AbstractGithubClient]:
        return self._clients

    async def execute(self, run: IntegrationRun) -> None:
        pass


def make_client(remaining: int, seconds_until_reset: float) -> MagicMock:
    client = MagicMock(spec=AbstractGithubClient)
    client.get_rate_limit_status.return_value = RateLimitInfo(
        remaining=remaining,
        limit=5000,
        reset_time=int(time.time()) + int(seconds_until_reset),
    )
    return client


@pytest.fixture
def run() -> IntegrationRun:
    return MagicMock(spec=IntegrationRun)


class TestAbstractGithubExecutorRateLimits:
    @pytest.mark.asyncio
    async def test_is_close_to_rate_limit_returns_false_when_no_clients(
        self, run: IntegrationRun
    ) -> None:
        executor = StubGithubExecutor([])

        assert await executor.is_close_to_rate_limit(run) is False

    @pytest.mark.asyncio
    async def test_is_close_to_rate_limit_requires_all_clients_to_be_close(
        self, run: IntegrationRun
    ) -> None:
        executor = StubGithubExecutor(
            [
                make_client(MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW - 1, 30),
                make_client(100, 10),
            ]
        )

        assert await executor.is_close_to_rate_limit(run) is False

        executor = StubGithubExecutor(
            [
                make_client(MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW - 1, 30),
                make_client(MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW, 10),
            ]
        )

        assert await executor.is_close_to_rate_limit(run) is False

        executor = StubGithubExecutor(
            [
                make_client(MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW - 1, 30),
                make_client(MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE_WORKFLOW - 1, 10),
            ]
        )

        assert await executor.is_close_to_rate_limit(run) is True

    @pytest.mark.asyncio
    async def test_get_remaining_seconds_until_rate_limit_returns_max(
        self, run: IntegrationRun
    ) -> None:
        executor = StubGithubExecutor(
            [
                make_client(100, 15.5),
                make_client(100, 42.0),
            ]
        )

        assert await executor.get_remaining_seconds_until_rate_limit(run) == 42.0

    @pytest.mark.asyncio
    async def test_get_remaining_seconds_until_rate_limit_returns_zero_without_clients(
        self, run: IntegrationRun
    ) -> None:
        executor = StubGithubExecutor([])

        assert await executor.get_remaining_seconds_until_rate_limit(run) == 0.0
