from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from actions.constants import ECHOING_STATUS_LABEL, MESSAGE_ECHOED_STATUS_LABEL
from actions.echo_message_executor import EchoMessageExecutor
from actions.exceptions import MissingExecutionPropertyError


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="fake-integration",
            integrationInvocationType="echo_message",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def executor() -> EchoMessageExecutor:
    return EchoMessageExecutor()


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.post_run_log = AsyncMock()
    client.report_run_completed = AsyncMock()
    return client


@pytest.mark.asyncio
class TestEchoMessageExecutor:
    async def test_happy_path(
        self, executor: EchoMessageExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run({"message": "hello smoke test"})
        with patch("actions.echo_message_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_port_client.post_run_log.assert_awaited_once_with(
            run,
            "Echoing message: hello smoke test",
            status_label=ECHOING_STATUS_LABEL,
            should_raise=False,
        )
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run,
            success=True,
            message="Echo: hello smoke test",
            status_label=MESSAGE_ECHOED_STATUS_LABEL,
        )

    async def test_missing_message(
        self, executor: EchoMessageExecutor, mock_port_client: MagicMock
    ) -> None:
        run = make_run({})
        with patch("actions.echo_message_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(MissingExecutionPropertyError) as exc_info:
                await executor.execute(run)

        assert exc_info.value.status_label == "Invalid input"
        mock_port_client.report_run_completed.assert_not_awaited()
