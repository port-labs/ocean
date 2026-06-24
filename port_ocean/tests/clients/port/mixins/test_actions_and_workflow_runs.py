from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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
class TestFindRunWithRetry:
    async def test_returns_run_on_first_try(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        with patch.object(
            actions_client,
            "find_run_by_external_id",
            AsyncMock(return_value=run),
        ):
            result = await actions_client.find_run_with_retry(EXTERNAL_ID)

        assert result is run

    async def test_retries_until_found(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        with (
            patch.object(
                actions_client,
                "find_run_by_external_id",
                AsyncMock(side_effect=[None, None, run]),
            ),
            patch(
                "port_ocean.clients.port.mixins.actions_and_workflow_runs.asyncio.sleep",
                AsyncMock(),
            ) as mock_sleep,
        ):
            result = await actions_client.find_run_with_retry(EXTERNAL_ID)

        assert result is run
        assert mock_sleep.await_count == 2

    async def test_returns_none_after_exhausting_retries(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        with (
            patch.object(
                actions_client,
                "find_run_by_external_id",
                AsyncMock(return_value=None),
            ),
            patch(
                "port_ocean.clients.port.mixins.actions_and_workflow_runs.asyncio.sleep",
                AsyncMock(),
            ),
        ):
            result = await actions_client.find_run_with_retry(EXTERNAL_ID)

        assert result is None

    async def test_retries_when_lookup_raises_http_error(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        run = make_run()
        response = MagicMock()
        response.status_code = 404
        http_error = httpx.HTTPStatusError(
            "404",
            request=MagicMock(),
            response=response,
        )
        with (
            patch.object(
                actions_client,
                "find_run_by_external_id",
                AsyncMock(side_effect=[http_error, http_error, run]),
            ),
            patch(
                "port_ocean.clients.port.mixins.actions_and_workflow_runs.asyncio.sleep",
                AsyncMock(),
            ) as mock_sleep,
        ):
            result = await actions_client.find_run_with_retry(EXTERNAL_ID)

        assert result is run
        assert mock_sleep.await_count == 2


@pytest.mark.asyncio
class TestFindRunByExternalId:
    async def test_returns_none_when_wf_node_lookup_raises(
        self, actions_client: ActionsAndWorkflowRunsClientMixin
    ) -> None:
        with (
            patch.object(
                actions_client,
                "get_run_by_external_id",
                AsyncMock(return_value=None),
            ),
            patch.object(
                actions_client,
                "get_wf_node_run_by_external_id",
                AsyncMock(
                    side_effect=httpx.HTTPStatusError(
                        "404",
                        request=MagicMock(),
                        response=MagicMock(status_code=404),
                    )
                ),
            ),
        ):
            result = await actions_client.find_run_by_external_id(EXTERNAL_ID)

        assert result is None


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
