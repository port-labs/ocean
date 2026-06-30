from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.clients.port.mixins.actions_and_workflow_runs import (
    ActionsAndWorkflowRunsClientMixin,
)
from port_ocean.core.models import (
    WorkflowNodeRun,
    WorkflowNodeRunResult,
    WorkflowNodeRunStatus,
)

EXTERNAL_ID = "gl_42_99"


def make_run() -> MagicMock:
    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run-1"
    run.status = WorkflowNodeRunStatus.IN_PROGRESS
    return run


@pytest.fixture
def actions_client() -> ActionsAndWorkflowRunsClientMixin:
    return ActionsAndWorkflowRunsClientMixin(auth=MagicMock(), client=MagicMock())


@pytest.mark.asyncio
class TestWorkflowNodeRunOutputPreservation:
    async def test_update_run_started_sets_run_output(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        with patch.object(
            actions_client, "patch_wf_node_run", AsyncMock()
        ) as mock_patch:
            await actions_client.update_run_started(
                run,
                "https://gitlab.example/pipelines/99",
                EXTERNAL_ID,
            )

        assert run.output == {"workflowRunUrl": "https://gitlab.example/pipelines/99"}
        mock_patch.assert_awaited_once_with(
            run.id,
            {
                "status": WorkflowNodeRunStatus.IN_PROGRESS,
                "externalRunId": EXTERNAL_ID,
                "output": {"workflowRunUrl": "https://gitlab.example/pipelines/99"},
            },
        )

    async def test_report_run_completed_preserves_output(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        run.output = {"workflowRunUrl": "https://gitlab.example/pipelines/99"}
        with (
            patch.object(
                actions_client, "patch_wf_node_run", AsyncMock()
            ) as mock_patch,
            patch.object(actions_client, "post_wf_node_run_logs", AsyncMock()),
        ):
            await actions_client.report_run_completed(run, True, "done")

        mock_patch.assert_awaited_once_with(
            run.id,
            {
                "status": WorkflowNodeRunStatus.COMPLETED,
                "result": WorkflowNodeRunResult.SUCCESS,
                "output": {"workflowRunUrl": "https://gitlab.example/pipelines/99"},
            },
        )

    async def test_report_run_failure_preserves_output(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        run.output = {"workflowRunUrl": "https://gitlab.example/pipelines/99"}
        with (
            patch.object(
                actions_client, "patch_wf_node_run", AsyncMock()
            ) as mock_patch,
            patch.object(actions_client, "post_wf_node_run_logs", AsyncMock()),
        ):
            await actions_client.report_run_failure(run, "pipeline failed")

        mock_patch.assert_awaited_once_with(
            run.id,
            {
                "status": WorkflowNodeRunStatus.COMPLETED,
                "result": WorkflowNodeRunResult.FAILED,
                "output": {"workflowRunUrl": "https://gitlab.example/pipelines/99"},
            },
            should_raise=False,
        )
