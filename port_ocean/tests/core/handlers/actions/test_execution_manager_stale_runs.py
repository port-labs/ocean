import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.actions.execution_manager import (
    STALE_RUNS_EXECUTOR_MIN_TIMEOUT,
    STALE_RUNS_MIN_LIMIT,
    STALE_RUNS_SWEEP_INTERVAL_MINUTES,
    ExecutionManager,
)
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
    StaleRunCloseDecision,
    StaleRunOutcome,
)


def _make_action_run(run_id: str = "run-1", action_type: str = "deploy") -> ActionRun:
    return ActionRun(
        id=run_id,
        status=RunStatus.IN_PROGRESS,
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType=action_type,
        ),
    )


@pytest.fixture
def execution_manager() -> ExecutionManager:
    signal_handler = MagicMock()
    signal_handler.register = MagicMock()
    return ExecutionManager(
        webhook_manager=MagicMock(),
        signal_handler=signal_handler,
        runs_buffer_high_watermark=100,
        workers_count=2,
        poll_check_interval_seconds=5,
        visibility_timeout_ms=30_000,
        max_wait_seconds_before_shutdown=10.0,
    )


class _BaseTestExecutor(AbstractExecutor):
    ACTION_NAME = "deploy"

    async def execute(self, run: ActionRun | Any) -> None:
        pass

    async def is_close_to_rate_limit(self) -> bool:
        return False

    async def get_remaining_seconds_until_rate_limit(self) -> float:
        return 999.0


def _executor_returning(
    decisions: list[StaleRunCloseDecision] | None,
) -> AbstractExecutor:
    class _E(_BaseTestExecutor):
        async def inspect_stale_runs(self, stale_runs: Any) -> Any:
            return decisions

    return _E()


class TestInspectStaleRunsForExecutor:
    async def test_returns_decisions(self, execution_manager: ExecutionManager) -> None:
        executor = _executor_returning(
            [
                StaleRunCloseDecision(
                    run_id="r1", outcome=StaleRunOutcome.FAILURE, summary="gone"
                )
            ]
        )
        result = await execution_manager._inspect_stale_runs_for_executor(
            "deploy", executor, [_make_action_run()], timeout_seconds=10.0
        )
        assert result is not None and result[0].run_id == "r1"

    async def test_returns_none_when_executor_opts_out(
        self, execution_manager: ExecutionManager
    ) -> None:
        result = await execution_manager._inspect_stale_runs_for_executor(
            "deploy",
            _executor_returning(None),
            [_make_action_run()],
            timeout_seconds=10.0,
        )
        assert result is None

    async def test_returns_none_on_executor_exception(
        self, execution_manager: ExecutionManager
    ) -> None:
        class _Broken(_BaseTestExecutor):
            async def inspect_stale_runs(self, stale_runs: Any) -> Any:
                raise RuntimeError("boom")

        result = await execution_manager._inspect_stale_runs_for_executor(
            "deploy", _Broken(), [_make_action_run()], timeout_seconds=10.0
        )
        assert result is None

    async def test_returns_none_on_timeout(
        self, execution_manager: ExecutionManager
    ) -> None:
        class _Slow(_BaseTestExecutor):
            async def inspect_stale_runs(self, stale_runs: Any) -> Any:
                await asyncio.sleep(999)
                return []

        result = await execution_manager._inspect_stale_runs_for_executor(
            "deploy", _Slow(), [_make_action_run()], timeout_seconds=0.01
        )
        assert result is None


class TestCloseStaleRun:
    async def test_skips_unknown_run_id(
        self, execution_manager: ExecutionManager
    ) -> None:
        with patch(
            "port_ocean.core.handlers.actions.execution_manager.ocean"
        ) as mock_ocean:
            mock_ocean.port_client.close_stale_run = AsyncMock()
            await execution_manager._close_stale_run(
                {},
                StaleRunCloseDecision(
                    run_id="ghost", outcome=StaleRunOutcome.FAILURE, summary="x"
                ),
            )
            mock_ocean.port_client.close_stale_run.assert_not_called()

    async def test_calls_close_on_known_run(
        self, execution_manager: ExecutionManager
    ) -> None:
        run = _make_action_run("r1")
        decision = StaleRunCloseDecision(
            run_id="r1", outcome=StaleRunOutcome.FAILURE, summary="timed out"
        )
        with patch(
            "port_ocean.core.handlers.actions.execution_manager.ocean"
        ) as mock_ocean:
            mock_ocean.port_client.close_stale_run = AsyncMock()
            await execution_manager._close_stale_run({"r1": run}, decision)
            mock_ocean.port_client.close_stale_run.assert_called_once_with(
                run, decision
            )

    async def test_swallows_api_errors(
        self, execution_manager: ExecutionManager
    ) -> None:
        run = _make_action_run("r1")
        with patch(
            "port_ocean.core.handlers.actions.execution_manager.ocean"
        ) as mock_ocean:
            mock_ocean.port_client.close_stale_run = AsyncMock(
                side_effect=RuntimeError("api down")
            )
            await execution_manager._close_stale_run(
                {"r1": run},
                StaleRunCloseDecision(
                    run_id="r1", outcome=StaleRunOutcome.FAILURE, summary="x"
                ),
            )


class TestSweepAdaptiveLimit:
    def test_halves_on_overrun_and_doubles_on_recovery(
        self, execution_manager: ExecutionManager
    ) -> None:
        high = execution_manager._high_watermark
        current = high

        current = max(STALE_RUNS_MIN_LIMIT, current // 2)
        assert current == 50

        current = max(STALE_RUNS_MIN_LIMIT, current // 2)
        assert current == 25

        current = min(high, current * 2)
        assert current == 50

        current = min(high, current * 2)
        assert current == high

    def test_floors_at_min(self) -> None:
        current = STALE_RUNS_MIN_LIMIT
        assert max(STALE_RUNS_MIN_LIMIT, current // 2) == STALE_RUNS_MIN_LIMIT

    def test_recovery_caps_at_high_watermark(
        self, execution_manager: ExecutionManager
    ) -> None:
        high = execution_manager._high_watermark
        current = min(high, (high // 2) * 2)
        assert current == high
        assert min(high, current * 2) == high


class TestPerExecutorTimeout:
    def test_single_executor_gets_full_interval(self) -> None:
        interval = STALE_RUNS_SWEEP_INTERVAL_MINUTES * 60
        assert max(STALE_RUNS_EXECUTOR_MIN_TIMEOUT, interval / 1) == interval

    def test_many_executors_floored_at_min(self) -> None:
        interval = STALE_RUNS_SWEEP_INTERVAL_MINUTES * 60
        assert (
            max(STALE_RUNS_EXECUTOR_MIN_TIMEOUT, interval / 10)
            == STALE_RUNS_EXECUTOR_MIN_TIMEOUT
        )

    def test_few_executors_above_floor(self) -> None:
        interval = STALE_RUNS_SWEEP_INTERVAL_MINUTES * 60
        assert max(STALE_RUNS_EXECUTOR_MIN_TIMEOUT, interval / 3) == 100.0
