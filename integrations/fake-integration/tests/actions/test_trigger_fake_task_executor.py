from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from actions.exceptions import MissingExecutionPropertyError, TriggerFakeTaskError
from actions.trigger_fake_task_executor import TriggerFakeTaskExecutor

TASK_RESPONSE = {
    "id": "task-123",
    "status": "pending",
    "link": "/fake-tasks/task-123",
}


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="fake-integration",
            integrationInvocationType="trigger_fake_task",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> TriggerFakeTaskExecutor:
    return TriggerFakeTaskExecutor()


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.update_run_started = AsyncMock()
    client.report_run_completed = AsyncMock()
    client.post_run_log = AsyncMock()
    return client


@pytest.mark.asyncio
class TestTriggerFakeTaskExecutor:
    async def test_happy_path(
        self, executor: TriggerFakeTaskExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run({"taskName": "smoke-task"})
        with (
            patch("actions.trigger_fake_task_executor.ocean") as mock_ocean,
            patch(
                "actions.trigger_fake_task_executor.trigger_fake_task",
                AsyncMock(return_value=TASK_RESPONSE),
            ),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_port_client.update_run_started.assert_awaited_once_with(
            run, TASK_RESPONSE["link"], "fake_task_task-123"
        )
        mock_port_client.report_run_completed.assert_not_awaited()

    async def test_missing_task_name(
        self, executor: TriggerFakeTaskExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run({})
        with patch("actions.trigger_fake_task_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError):
                await executor.execute(run)

    async def test_upstream_error(
        self, executor: TriggerFakeTaskExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run({"taskName": "smoke-task"})
        with (
            patch("actions.trigger_fake_task_executor.ocean") as mock_ocean,
            patch(
                "actions.trigger_fake_task_executor.trigger_fake_task",
                AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            mock_ocean.port_client = mock_port_client
            with pytest.raises(TriggerFakeTaskError):
                await executor.execute(run)
