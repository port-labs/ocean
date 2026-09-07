import time

import pytest

from linear.actions.abstract_linear_executor import AbstractLinearExecutor
from linear.client.rate_limiter import (
    LinearRateLimitStatus,
    parse_rate_limit_headers,
)
from port_ocean.core.models import (
    IntegrationRun,
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)


def test_parse_rate_limit_headers() -> None:
    headers = {
        "X-RateLimit-Requests-Remaining": "42",
        "X-RateLimit-Complexity-Remaining": "9000",
        "X-RateLimit-Requests-Reset": "2000",
        "X-RateLimit-Complexity-Reset": "3000",
    }

    status = parse_rate_limit_headers(headers)

    assert status.requests_remaining == 42
    assert status.complexity_remaining == 9000
    assert status.requests_reset_at_ms == 2000
    assert status.complexity_reset_at_ms == 3000


def test_is_close_to_limit_when_requests_are_low() -> None:
    status = LinearRateLimitStatus(
        requests_remaining=5,
        complexity_remaining=50_000,
        requests_reset_at_ms=None,
        complexity_reset_at_ms=None,
    )

    assert status.is_close_to_limit()


def test_seconds_until_reset_uses_earliest_future_reset() -> None:
    now_ms = int(time.time() * 1000)
    status = LinearRateLimitStatus(
        requests_remaining=100,
        complexity_remaining=100,
        requests_reset_at_ms=now_ms + 5_000,
        complexity_reset_at_ms=now_ms + 2_000,
    )

    assert 1.0 <= status.seconds_until_reset() <= 2.5


@pytest.mark.asyncio
async def test_executor_rate_limit_checks_use_client_status() -> None:
    class StubExecutor(AbstractLinearExecutor):
        ACTION_NAME = "create_issue"

        async def execute(self, run: IntegrationRun) -> None:
            return None

    executor = StubExecutor.__new__(StubExecutor)
    executor.client = type(
        "ClientStub",
        (),
        {
            "get_rate_limit_status": lambda self: LinearRateLimitStatus(
                requests_remaining=1,
                complexity_remaining=100_000,
                requests_reset_at_ms=int(time.time() * 1000) + 10_000,
                complexity_reset_at_ms=None,
            )
        },
    )()

    run = WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="linear",
            integrationInvocationType="create_issue",
            integrationActionExecutionProperties={},
        ),
    )

    assert await executor.is_close_to_rate_limit(run) is True
    assert await executor.get_remaining_seconds_until_rate_limit(run) > 0
