from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

from port_ocean.clients.port.mixins.actions_and_workflow_runs import (
    ActionsAndWorkflowRunsClientMixin,
)
from port_ocean.core.models import (
    ActionRun,
    ClaimedWorkflowNodeRun,
    IntegrationActionInvocationPayload,
    RunStatus,
    StaleRunCloseDecision,
    StaleRunOutcome,
    WorkflowNodeRunResult,
    WorkflowNodeRunStatus,
)


@dataclass
class _MixinFixture:
    mixin: ActionsAndWorkflowRunsClientMixin
    patch_run: AsyncMock
    patch_wf_node_run: AsyncMock
    post_wf_node_run_logs: AsyncMock


def _make_mixin() -> _MixinFixture:
    mixin = ActionsAndWorkflowRunsClientMixin(auth=MagicMock(), client=MagicMock())
    patch_run = AsyncMock()
    patch_wf_node_run = AsyncMock()
    post_wf_node_run_logs = AsyncMock()
    mixin.patch_run = patch_run  # type: ignore[method-assign]
    mixin.patch_wf_node_run = patch_wf_node_run  # type: ignore[method-assign]
    mixin.post_wf_node_run_logs = post_wf_node_run_logs  # type: ignore[method-assign]
    return _MixinFixture(mixin, patch_run, patch_wf_node_run, post_wf_node_run_logs)


def _action_run(run_id: str = "r1") -> ActionRun:
    return ActionRun(
        id=run_id,
        status=RunStatus.IN_PROGRESS,
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="deploy",
        ),
    )


def _wf_node_run(run_id: str = "wf-1") -> ClaimedWorkflowNodeRun:
    return ClaimedWorkflowNodeRun(
        identifier=run_id,
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config={
            "integrationInvocationType": "deploy",
            "integrationActionExecutionProperties": {},
        },
    )


class TestCloseStaleRunActionRun:
    async def test_success(self) -> None:
        f = _make_mixin()
        await f.mixin.close_stale_run(
            _action_run(),
            StaleRunCloseDecision(
                run_id="r1", outcome=StaleRunOutcome.SUCCESS, summary="ok"
            ),
        )
        f.patch_run.assert_awaited_once_with(
            "r1", {"status": RunStatus.SUCCESS, "summary": "ok"}, should_raise=False
        )
        f.patch_wf_node_run.assert_not_awaited()

    async def test_failure(self) -> None:
        f = _make_mixin()
        await f.mixin.close_stale_run(
            _action_run(),
            StaleRunCloseDecision(
                run_id="r1", outcome=StaleRunOutcome.FAILURE, summary="timeout"
            ),
        )
        f.patch_run.assert_awaited_once_with(
            "r1",
            {"status": RunStatus.FAILURE, "summary": "timeout"},
            should_raise=False,
        )

    async def test_cancelled_falls_back_to_failure(self) -> None:
        f = _make_mixin()
        await f.mixin.close_stale_run(
            _action_run(),
            StaleRunCloseDecision(
                run_id="r1", outcome=StaleRunOutcome.CANCELLED, summary="cancelled"
            ),
        )
        f.patch_run.assert_awaited_once_with(
            "r1",
            {"status": RunStatus.FAILURE, "summary": "cancelled"},
            should_raise=False,
        )


class TestCloseStaleRunWorkflowNodeRun:
    async def test_success(self) -> None:
        f = _make_mixin()
        await f.mixin.close_stale_run(
            _wf_node_run(),
            StaleRunCloseDecision(
                run_id="wf-1", outcome=StaleRunOutcome.SUCCESS, summary="done"
            ),
        )
        f.post_wf_node_run_logs.assert_awaited_once()
        f.patch_wf_node_run.assert_awaited_once_with(
            "wf-1",
            {
                "status": WorkflowNodeRunStatus.COMPLETED,
                "result": WorkflowNodeRunResult.SUCCESS,
            },
            should_raise=False,
        )
        f.patch_run.assert_not_awaited()

    async def test_failure(self) -> None:
        f = _make_mixin()
        await f.mixin.close_stale_run(
            _wf_node_run(),
            StaleRunCloseDecision(
                run_id="wf-1", outcome=StaleRunOutcome.FAILURE, summary="timeout"
            ),
        )
        f.patch_wf_node_run.assert_awaited_once_with(
            "wf-1",
            {
                "status": WorkflowNodeRunStatus.COMPLETED,
                "result": WorkflowNodeRunResult.FAILED,
            },
            should_raise=False,
        )

    async def test_cancelled(self) -> None:
        f = _make_mixin()
        await f.mixin.close_stale_run(
            _wf_node_run(),
            StaleRunCloseDecision(
                run_id="wf-1", outcome=StaleRunOutcome.CANCELLED, summary="cancelled"
            ),
        )
        f.patch_wf_node_run.assert_awaited_once_with(
            "wf-1",
            {
                "status": WorkflowNodeRunStatus.COMPLETED,
                "result": WorkflowNodeRunResult.CANCELLED,
            },
            should_raise=False,
        )

    async def test_log_posted_before_patch(self) -> None:
        f = _make_mixin()
        order: list[str] = []
        f.post_wf_node_run_logs.side_effect = lambda *a, **kw: order.append("log")
        f.patch_wf_node_run.side_effect = lambda *a, **kw: order.append("patch")

        await f.mixin.close_stale_run(
            _wf_node_run(),
            StaleRunCloseDecision(
                run_id="wf-1", outcome=StaleRunOutcome.FAILURE, summary="x"
            ),
        )
        assert order == ["log", "patch"]
