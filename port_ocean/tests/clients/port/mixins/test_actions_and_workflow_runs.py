from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.clients.port.mixins.actions_and_workflow_runs import (
    ActionsAndWorkflowRunsClientMixin,
)
from port_ocean.core.models import WorkflowNodeRun, WorkflowNodeRunStatus

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
