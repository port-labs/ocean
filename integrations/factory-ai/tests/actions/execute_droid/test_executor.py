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

from factory_ai.actions.exceptions import (
    ExecuteDroidError,
    InvalidActionParametersError,
)
from factory_ai.actions.execute_droid.executor import (
    TURN_ACCEPTED_STATUS_LABEL,
    ExecuteDroidExecutor,
)
from factory_ai.actions.execute_droid.models import ExecuteDroidResponse
from factory_ai.clients.exceptions import FactoryAIError

EXECUTE_RESPONSE = ExecuteDroidResponse.model_validate(
    {
        "sessionId": "sess-1",
        "computerId": "comp-1",
        "messageId": "msg-1",
    }
)

SESSION_RAW = {
    "sessionId": "sess-1",
    "status": "running",
    "messageCount": 1,
    "createdAt": 1_700_000_000_000,
    "updatedAt": 1_700_000_100_000,
    "computerId": "comp-1",
}

_EXECUTOR_MODULE = "factory_ai.actions.execute_droid.executor"


def make_run(execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="factory-ai",
            integrationInvocationType="execute_droid",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def client() -> MagicMock:
    mock = MagicMock()
    mock.post = AsyncMock(return_value=EXECUTE_RESPONSE)
    return mock


@pytest.fixture
def executor(client: MagicMock) -> ExecuteDroidExecutor:
    instance = ExecuteDroidExecutor()
    instance._client = client
    return instance


@pytest.fixture
def mock_port_client() -> MagicMock:
    mock = MagicMock()
    mock.update_run_started = AsyncMock()
    mock.report_run_completed = AsyncMock()
    mock.post_run_log = AsyncMock()
    return mock


@pytest.mark.asyncio
class TestExecuteDroidExecutor:
    async def test_happy_path_environment(
        self,
        executor: ExecuteDroidExecutor,
        client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "prompt": "Fix the flaky test",
                "targetKind": "environment",
                "environmentId": "env-1",
            }
        )
        with (
            patch(f"{_EXECUTOR_MODULE}.ocean") as mock_ocean,
            patch.object(
                executor,
                "_reflect_session",
                new_callable=AsyncMock,
            ) as reflect,
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        client.post.assert_awaited_once_with(
            "/api/v0/droid/execute",
            ExecuteDroidResponse,
            json_body={
                "prompt": "Fix the flaky test",
                "target": {"kind": "environment", "environmentId": "env-1"},
            },
        )
        reflect.assert_awaited_once_with("sess-1", "comp-1", run)
        mock_port_client.update_run_started.assert_not_called()
        mock_port_client.report_run_completed.assert_called_once()
        args, kwargs = mock_port_client.report_run_completed.call_args
        assert args[0] is run
        assert args[1] is True
        assert "sess-1" in args[2]
        assert "msg-1" in args[2]
        assert kwargs["status_label"] == TURN_ACCEPTED_STATUS_LABEL
        assert run.output["sessionId"] == "sess-1"
        assert run.output["messageId"] == "msg-1"
        assert run.output["computerId"] == "comp-1"
        assert run.output["sessionUrl"] == "https://app.factory.ai/sessions/sess-1"
        assert run.output["computerUrl"] == "https://app.factory.ai/computers/comp-1"

    async def test_happy_path_session_follow_up(
        self,
        executor: ExecuteDroidExecutor,
        client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run(
            {
                "prompt": "Also add tests",
                "targetKind": "session",
                "sessionId": "sess-1",
            }
        )
        with (
            patch(f"{_EXECUTOR_MODULE}.ocean") as mock_ocean,
            patch.object(executor, "_reflect_session", new_callable=AsyncMock),
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        client.post.assert_awaited_once_with(
            "/api/v0/droid/execute",
            ExecuteDroidResponse,
            json_body={
                "prompt": "Also add tests",
                "target": {"kind": "session", "sessionId": "sess-1"},
            },
        )

    async def test_missing_required_input(
        self,
        executor: ExecuteDroidExecutor,
        client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        run = make_run({"prompt": "hi", "targetKind": "computer"})
        with patch(f"{_EXECUTOR_MODULE}.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(InvalidActionParametersError):
                await executor.execute(run)
        client.post.assert_not_called()

    async def test_upstream_http_error(
        self,
        executor: ExecuteDroidExecutor,
        client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        response = httpx.Response(
            403,
            json={
                "detail": "Sessions API not enabled",
                "status": 403,
                "title": "Forbidden",
            },
            request=httpx.Request(
                "POST", "https://api.factory.ai/api/v0/droid/execute"
            ),
        )
        client.post.side_effect = httpx.HTTPStatusError(
            "403", request=response.request, response=response
        )
        run = make_run(
            {
                "prompt": "hi",
                "targetKind": "environment",
                "environmentId": "env-1",
            }
        )
        with patch(f"{_EXECUTOR_MODULE}.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(ExecuteDroidError, match="Sessions API not enabled"):
                await executor.execute(run)

        mock_port_client.report_run_completed.assert_not_called()

    async def test_malformed_upstream_response(
        self,
        executor: ExecuteDroidExecutor,
        client: MagicMock,
        mock_port_client: MagicMock,
    ) -> None:
        client.post.side_effect = FactoryAIError(
            "Invalid Factory response for POST /api/v0/droid/execute: ..."
        )
        run = make_run(
            {
                "prompt": "hi",
                "targetKind": "computer",
                "computerId": "comp-1",
            }
        )
        with patch(f"{_EXECUTOR_MODULE}.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            with pytest.raises(ExecuteDroidError):
                await executor.execute(run)

    async def test_partition_key_for_session(
        self, executor: ExecuteDroidExecutor
    ) -> None:
        run = make_run(
            {
                "prompt": "hi",
                "targetKind": "session",
                "sessionId": "sess-9",
            }
        )
        assert await executor._get_partition_key(run) == "sess-9"

    async def test_partition_key_missing_returns_none(
        self, executor: ExecuteDroidExecutor
    ) -> None:
        assert await executor._get_partition_key(make_run({})) is None

    async def test_reflect_session_registers_when_readable(
        self, executor: ExecuteDroidExecutor
    ) -> None:
        run = make_run(
            {
                "prompt": "hi",
                "targetKind": "environment",
                "environmentId": "env-1",
            }
        )
        with (
            patch(f"{_EXECUTOR_MODULE}.SessionExporter") as exporter_cls,
            patch.object(
                executor, "register_entity", new_callable=AsyncMock
            ) as register,
        ):
            exporter_cls.return_value.get_resource = AsyncMock(return_value=SESSION_RAW)
            await executor._reflect_session("sess-1", "comp-1", run)

        register.assert_awaited_once_with("session", SESSION_RAW, run)

    async def test_reflect_session_skips_when_unreadable(
        self, executor: ExecuteDroidExecutor
    ) -> None:
        run = make_run(
            {
                "prompt": "hi",
                "targetKind": "environment",
                "environmentId": "env-1",
            }
        )
        with (
            patch(f"{_EXECUTOR_MODULE}.SessionExporter") as exporter_cls,
            patch.object(
                executor, "register_entity", new_callable=AsyncMock
            ) as register,
        ):
            exporter_cls.return_value.get_resource = AsyncMock(return_value=None)
            await executor._reflect_session("sess-1", "comp-1", run)

        register.assert_not_called()


def test_execute_droid_error_from_response_prefers_detail() -> None:
    response = httpx.Response(
        409,
        json={"detail": "Computer busy", "status": 409, "title": "Conflict"},
        request=httpx.Request("POST", "https://api.factory.ai/api/v0/droid/execute"),
    )
    error = ExecuteDroidError.from_response(response, "Could not execute")
    assert str(error) == "Could not execute: Computer busy"
