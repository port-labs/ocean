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
    TURN_COMPLETED_STATUS_LABEL,
    TURN_TIMED_OUT_STATUS_LABEL,
    ExecuteDroidExecutor,
    TurnCompletion,
)
from factory_ai.actions.execute_droid.models import (
    ExecuteDroidResponse,
    ListSessionMessagesResponse,
    SessionMessage,
)
from factory_ai.clients.exceptions import FactoryAIError
from factory_ai.core.exporters.session.models import Session

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
    mock.get = AsyncMock()
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


def _messages_response(
    messages: list[SessionMessage],
) -> ListSessionMessagesResponse:
    return ListSessionMessagesResponse.model_validate(
        {"messages": messages, "pagination": {"hasMore": False}}
    )


def test_assistant_reply_after_empty_when_no_assistant_yet() -> None:
    response = _messages_response(
        [
            SessionMessage.model_validate({"id": "msg-1", "role": "user"}),
        ]
    )
    assert response.assistant_reply_after("msg-1") == {}


def test_assistant_reply_after_joins_text_chronologically() -> None:
    response = _messages_response(
        [
            SessionMessage.model_validate(
                {
                    "id": "msg-3",
                    "role": "assistant",
                    "modelId": "claude-sonnet",
                    "content": [{"type": "text", "text": "second"}],
                }
            ),
            SessionMessage.model_validate(
                {
                    "id": "msg-2",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "bash",
                            "id": "tool-1",
                            "input": {},
                        },
                        {"type": "text", "text": "first"},
                    ],
                }
            ),
            SessionMessage.model_validate({"id": "msg-1", "role": "user"}),
        ]
    )
    reply = response.assistant_reply_after("msg-1")
    assert reply == {
        "assistantMessageIds": ["msg-2", "msg-3"],
        "assistantMessageId": "msg-3",
        "assistantText": "first\n\nsecond",
        "toolNames": ["bash"],
        "modelId": "claude-sonnet",
        "assistantIsError": False,
    }


def test_assistant_reply_after_includes_empty_fields() -> None:
    response = _messages_response(
        [
            SessionMessage.model_validate(
                {"id": "msg-2", "role": "assistant", "content": []}
            ),
            SessionMessage.model_validate({"id": "msg-1", "role": "user"}),
        ]
    )
    reply = response.assistant_reply_after("msg-1")
    assert reply == {
        "assistantMessageIds": ["msg-2"],
        "assistantMessageId": "msg-2",
        "assistantText": "",
        "toolNames": [],
        "modelId": None,
        "assistantIsError": False,
    }


@pytest.mark.asyncio
class TestExecuteDroidExecutor:
    async def test_happy_path_without_waiting(
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
                "waitForCompletion": False,
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

    async def test_happy_path_session_follow_up_without_waiting(
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
                "waitForCompletion": False,
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

    async def test_waits_for_completion_by_default(
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
        completion = TurnCompletion(
            session=Session.model_validate(
                {
                    "sessionId": "sess-1",
                    "title": "Fix the flaky test",
                    "status": "idle",
                    "messageCount": 2,
                    "createdAt": 1,
                    "updatedAt": 2,
                    "computerId": "comp-1",
                    "factoryCredits": 1.25,
                    "sessionSettings": {"model": "claude-sonnet"},
                    "artifacts": [
                        {
                            "id": "art-1",
                            "url": "https://github.com/org/repo/pull/1",
                            "provider": "github",
                            "kind": "pull_request",
                            "source": "tool",
                            "createdAt": "2024-01-01T00:00:00.000Z",
                        }
                    ],
                }
            ),
            reply={
                "assistantText": "Done — PR opened.",
                "assistantMessageId": "msg-2",
                "assistantMessageIds": ["msg-2"],
            },
            user_message_id="msg-1",
        )
        with (
            patch(f"{_EXECUTOR_MODULE}.ocean") as mock_ocean,
            patch.object(executor, "_reflect_session", new_callable=AsyncMock),
            patch.object(
                executor,
                "_wait_for_turn_completion",
                new_callable=AsyncMock,
                return_value=completion,
            ) as wait,
        ):
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        wait.assert_awaited_once_with("sess-1", "comp-1", "msg-1")
        mock_port_client.update_run_started.assert_called_once()
        mock_port_client.report_run_completed.assert_called_once()
        args, kwargs = mock_port_client.report_run_completed.call_args
        assert kwargs["status_label"] == TURN_COMPLETED_STATUS_LABEL
        assert "Done — PR opened." in args[2]
        assert run.output["assistantText"] == "Done — PR opened."
        assert run.output["assistantMessageId"] == "msg-2"
        assert run.output["title"] == "Fix the flaky test"
        assert run.output["status"] == "idle"
        assert run.output["factoryCredits"] == 1.25
        assert run.output["sessionSettings"]["model"] == "claude-sonnet"
        assert run.output["artifacts"][0]["kind"] == "pull_request"

    async def test_wait_for_turn_completion_polls_until_done(
        self, executor: ExecuteDroidExecutor, client: MagicMock
    ) -> None:
        idle_session = Session.model_validate(
            {
                "sessionId": "sess-1",
                "status": "idle",
                "messageCount": 2,
                "createdAt": 1,
                "updatedAt": 2,
                "computerId": "comp-1",
                "title": "Ship it",
            }
        )
        running_session = Session.model_validate(
            {
                "sessionId": "sess-1",
                "status": "running",
                "messageCount": 1,
                "createdAt": 1,
                "updatedAt": 2,
                "computerId": "comp-1",
            }
        )
        messages = ListSessionMessagesResponse.model_validate(
            {
                "messages": [
                    {
                        "id": "msg-2",
                        "role": "assistant",
                        "content": [{"type": "text", "text": "All green."}],
                    },
                    {"id": "msg-1", "role": "user"},
                ],
                "pagination": {"hasMore": False, "nextCursor": None},
            }
        )
        client.get.side_effect = [
            running_session,
            idle_session,
            messages,
        ]

        with patch(f"{_EXECUTOR_MODULE}.asyncio.sleep", new_callable=AsyncMock):
            completion = await executor._wait_for_turn_completion(
                "sess-1", "comp-1", "msg-1"
            )

        assert client.get.await_count == 3
        assert completion.session.title == "Ship it"
        assert completion.reply["assistantText"] == "All green."
        assert completion.reply["assistantMessageId"] == "msg-2"

    async def test_wait_for_turn_completion_times_out(
        self, executor: ExecuteDroidExecutor, client: MagicMock
    ) -> None:
        running_session = Session.model_validate(
            {
                "sessionId": "sess-1",
                "status": "running",
                "messageCount": 1,
                "createdAt": 1,
                "updatedAt": 2,
                "computerId": "comp-1",
            }
        )
        client.get.return_value = running_session

        with (
            patch(f"{_EXECUTOR_MODULE}.asyncio.sleep", new_callable=AsyncMock),
            patch(f"{_EXECUTOR_MODULE}.MAX_POLL_ATTEMPTS", 2),
            pytest.raises(ExecuteDroidError, match="Timed out") as raised,
        ):
            await executor._wait_for_turn_completion("sess-1", "comp-1", "msg-1")

        assert raised.value.status_label == TURN_TIMED_OUT_STATUS_LABEL

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
                "waitForCompletion": False,
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
                "waitForCompletion": False,
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
