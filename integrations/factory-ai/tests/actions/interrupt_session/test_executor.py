from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from factory_ai.actions.exceptions import InterruptSessionError
from factory_ai.actions.interrupt_session.executor import (
    SESSION_INTERRUPTED_STATUS_LABEL,
    InterruptSessionExecutor,
)
from factory_ai.actions.interrupt_session.models import InterruptSessionResponse

_EXECUTOR_MODULE = "factory_ai.actions.interrupt_session.executor"

INTERRUPT_RESPONSE = InterruptSessionResponse.model_validate({"status": "idle"})


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="factory-ai",
            integrationInvocationType="interrupt_session",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def client() -> MagicMock:
    mock = MagicMock()
    mock.post = AsyncMock(return_value=INTERRUPT_RESPONSE)
    return mock


@pytest.fixture
def executor(client: MagicMock) -> InterruptSessionExecutor:
    instance = InterruptSessionExecutor()
    instance._client = client
    return instance


@pytest.fixture
def mock_port_client() -> MagicMock:
    mock = MagicMock()
    mock.post_run_log = AsyncMock()
    mock.report_run_completed = AsyncMock()
    return mock


class TestInterruptSessionExecutor:
    async def test_happy_path(
        self,
        executor: InterruptSessionExecutor,
        client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run({"sessionId": "sess-1"})
        with (
            patch(f"{_EXECUTOR_MODULE}.ocean") as mock_ocean,
            patch.object(
                executor, "_reflect_session", new_callable=AsyncMock
            ) as reflect,
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        client.post.assert_awaited_once_with(
            "/api/v0/sessions/sess-1/interrupt",
            InterruptSessionResponse,
        )
        reflect.assert_awaited_once_with("sess-1", run)
        mock_port_client.report_run_completed.assert_called_once()
        args, kwargs = mock_port_client.report_run_completed.call_args
        assert args[1] is True
        assert kwargs["status_label"] == SESSION_INTERRUPTED_STATUS_LABEL
        assert run.output["sessionId"] == "sess-1"
        assert run.output["status"] == "idle"
        assert run.output["sessionUrl"] == "https://app.factory.ai/sessions/sess-1"

    async def test_http_error_maps_to_interrupt_session_error(
        self,
        executor: InterruptSessionExecutor,
        client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        request = httpx.Request(
            "POST", "https://api.factory.ai/api/v0/sessions/sess-1/interrupt"
        )
        response = httpx.Response(
            404, json={"detail": "Session not found"}, request=request
        )
        client.post.side_effect = httpx.HTTPStatusError(
            "not found", request=request, response=response
        )
        run = make_run({"sessionId": "sess-1"})
        with patch(f"{_EXECUTOR_MODULE}.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(InterruptSessionError, match="Session not found"):
                await executor.execute(run)

    async def test_partition_key_is_session_id(
        self, executor: InterruptSessionExecutor
    ) -> None:
        run = make_run({"sessionId": "sess-9"})
        assert await executor._get_partition_key(run) == "sess-9"
