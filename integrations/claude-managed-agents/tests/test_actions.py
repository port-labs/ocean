from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, AsyncIterator, TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_text_block import (
    BetaManagedAgentsTextBlock,
)
from actions.abstract_executor import AbstractAnthropicExecutor
from actions.create_agent_executor import CreateAgentExecutor
from actions.session_config import normalize_session_config
from actions.trigger_agent_executor import TriggerAgentExecutor
from actions.utils import build_external_id, build_session_link

T = TypeVar("T", bound=AbstractAnthropicExecutor)


@asynccontextmanager
async def _noop_event_context(*args: Any, **kwargs: Any) -> AsyncIterator[None]:
    yield


def _build_executor(executor_cls: type[T], client_mock: MagicMock) -> T:
    with patch(
        "actions.abstract_executor.create_anthropic_client", return_value=client_mock
    ):
        return executor_cls()


def _build_mock_ocean() -> MagicMock:
    mock_ocean = MagicMock()
    mock_ocean.config.port = SimpleNamespace(base_url="https://api.getport.io")
    mock_ocean.register_raw = AsyncMock()
    mock_ocean.integration.port_app_config_handler.get_port_app_config = AsyncMock()
    return mock_ocean


def test_build_external_id() -> None:
    assert build_external_id("s1", "evt_1") == "claude_session_s1_evt_1"


def test_build_session_link() -> None:
    assert (
        build_session_link("ws_1", "s1")
        == "https://platform.claude.com/workspaces/ws_1/sessions/s1"
    )


def test_build_session_link_falls_back_without_workspace_id() -> None:
    assert build_session_link(None, "s1") == "https://platform.claude.com/"


@pytest.mark.asyncio
async def test_is_close_to_rate_limit_false_when_no_status_cached() -> None:
    client_mock = MagicMock()
    client_mock.get_create_rate_limit_status.return_value = None
    executor = _build_executor(CreateAgentExecutor, client_mock)

    assert await executor.is_close_to_rate_limit() is False


@pytest.mark.asyncio
async def test_is_close_to_rate_limit_false_with_healthy_headroom() -> None:
    from clients.anthropic_client import CreateRateLimitInfo
    from datetime import datetime, timedelta, timezone

    client_mock = MagicMock()
    client_mock.get_create_rate_limit_status.return_value = CreateRateLimitInfo(
        limit=300,
        remaining=250,
        reset=datetime.now(timezone.utc) + timedelta(seconds=30),
    )
    executor = _build_executor(CreateAgentExecutor, client_mock)

    assert await executor.is_close_to_rate_limit() is False


@pytest.mark.asyncio
async def test_is_close_to_rate_limit_true_when_nearly_exhausted() -> None:
    from clients.anthropic_client import CreateRateLimitInfo
    from datetime import datetime, timedelta, timezone

    client_mock = MagicMock()
    client_mock.get_create_rate_limit_status.return_value = CreateRateLimitInfo(
        limit=300,
        remaining=20,
        reset=datetime.now(timezone.utc) + timedelta(seconds=30),
    )
    executor = _build_executor(CreateAgentExecutor, client_mock)

    assert await executor.is_close_to_rate_limit() is True


@pytest.mark.asyncio
async def test_get_remaining_seconds_until_rate_limit_zero_when_no_status_cached() -> (
    None
):
    client_mock = MagicMock()
    client_mock.get_create_rate_limit_status.return_value = None
    executor = _build_executor(CreateAgentExecutor, client_mock)

    assert await executor.get_remaining_seconds_until_rate_limit() == 0.0


@pytest.mark.asyncio
async def test_get_remaining_seconds_until_rate_limit_matches_reset_window() -> None:
    from clients.anthropic_client import CreateRateLimitInfo
    from datetime import datetime, timedelta, timezone

    reset_at = datetime.now(timezone.utc) + timedelta(seconds=42)
    client_mock = MagicMock()
    client_mock.get_create_rate_limit_status.return_value = CreateRateLimitInfo(
        limit=300, remaining=1, reset=reset_at
    )
    executor = _build_executor(CreateAgentExecutor, client_mock)

    remaining = await executor.get_remaining_seconds_until_rate_limit()
    assert 40 <= remaining <= 42


@pytest.mark.asyncio
async def test_is_close_to_rate_limit_false_once_reset_time_has_passed() -> None:
    """A stale cache past its reset must not wedge the execution manager's
    backoff loop forever: nothing refreshes the cache while backing off, so a
    passed reset has to be treated as fully replenished."""
    from clients.anthropic_client import CreateRateLimitInfo
    from datetime import datetime, timedelta, timezone

    stale_reset = datetime.now(timezone.utc) - timedelta(seconds=5)
    client_mock = MagicMock()
    client_mock.get_create_rate_limit_status.return_value = CreateRateLimitInfo(
        limit=300, remaining=1, reset=stale_reset
    )
    executor = _build_executor(CreateAgentExecutor, client_mock)

    assert await executor.is_close_to_rate_limit() is False


@pytest.mark.asyncio
async def test_create_agent_executor_creates_and_completes() -> None:
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(return_value={"id": "agent_1"})
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "name": "n",
        "model": "m",
        "systemPrompt": "s",
        "config": {"description": "d"},
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _noop_event_context),
    ):
        await executor.execute(run)

    client_mock.create_agent.assert_awaited_once_with(
        name="n", model="m", system="s", extra={"description": "d"}
    )
    mock_ocean.register_raw.assert_awaited_once()
    mock_ocean.port_client.report_run_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_agent_executor_passes_config_through() -> None:
    """Config (including MCP servers declared by the workflow) is passed through unchanged."""
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(return_value={"id": "agent_1"})
    executor = _build_executor(CreateAgentExecutor, client_mock)

    mcp_config = {
        "mcp_servers": [
            {"type": "url", "name": "port", "url": "https://mcp.port.io/v1"}
        ],
        "tools": [
            {
                "type": "mcp_toolset",
                "mcp_server_name": "port",
                "default_config": {"permission_policy": {"type": "always_allow"}},
            }
        ],
    }
    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "name": "n",
        "model": "claude-opus-4-8",
        "systemPrompt": "s",
        "config": mcp_config,
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _noop_event_context),
    ):
        await executor.execute(run)

    client_mock.create_agent.assert_awaited_once_with(
        name="n",
        model="claude-opus-4-8",
        system="s",
        extra=mcp_config,
    )


@pytest.mark.asyncio
async def test_create_agent_executor_passes_skills_config_through() -> None:
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(return_value={"id": "agent_1"})
    executor = _build_executor(CreateAgentExecutor, client_mock)

    skills = [{"type": "custom", "skill_id": "skill_01"}]
    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "name": "n",
        "model": "m",
        "systemPrompt": "s",
        "config": {"skills": skills},
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _noop_event_context),
    ):
        await executor.execute(run)

    client_mock.create_agent.assert_awaited_once_with(
        name="n",
        model="m",
        system="s",
        extra={"skills": skills},
    )


@pytest.mark.asyncio
async def test_create_agent_executor_reports_failure_on_api_error() -> None:
    client_mock = MagicMock()
    client_mock.create_agent = AsyncMock(side_effect=RuntimeError("quota exceeded"))
    executor = _build_executor(CreateAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {"name": "n", "model": "m"}

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.create_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _noop_event_context),
    ):
        await executor.execute(run)

    call = mock_ocean.port_client.report_run_completed.call_args
    assert call.args[1] is False
    assert "quota exceeded" in call.args[2]
    mock_ocean.register_raw.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_agent_executor_requires_name_and_model() -> None:
    executor = _build_executor(CreateAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"name": "only-name"}
    with pytest.raises(ValueError):
        await executor.execute(run)


def _user_message_event(event_id: str = "msg_1") -> BetaManagedAgentsUserMessageEvent:
    return BetaManagedAgentsUserMessageEvent(
        id=event_id,
        type="user.message",
        content=[BetaManagedAgentsTextBlock(type="text", text="go")],
    )


@pytest.mark.asyncio
async def test_trigger_agent_executor_starts_session() -> None:
    client_mock = MagicMock()
    client_mock.create_session = AsyncMock(return_value={"id": "sess_1"})
    client_mock.send_user_message = AsyncMock(return_value=_user_message_event())
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("actions.trigger_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _noop_event_context),
    ):
        await executor.execute(run)

    client_mock.create_session.assert_awaited_once_with("agent_1", "env_1", extra=None)
    client_mock.send_user_message.assert_awaited_once_with("sess_1", "go")
    mock_ocean.register_raw.assert_awaited_once()
    mock_ocean.port_client.update_run_started.assert_awaited_once()
    call = mock_ocean.port_client.update_run_started.call_args
    assert call.args[2] == "claude_session_sess_1_msg_1"
    assert call.kwargs["extra_output"] == {
        "sessionId": "sess_1",
        "userMessageEventId": "msg_1",
    }


@pytest.mark.asyncio
async def test_trigger_agent_executor_passes_config_on_new_session() -> None:
    client_mock = MagicMock()
    client_mock.create_session = AsyncMock(return_value={"id": "sess_1"})
    client_mock.send_user_message = AsyncMock(return_value=_user_message_event())
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
        "config": {
            "title": "My session",
            "metadata": {"team": "platform"},
            "vault_ids": ["vault_1"],
            "resources": [{"type": "memory_store", "memory_store_id": "ms_1"}],
        },
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("actions.trigger_agent_executor.ocean", mock_ocean),
        patch("actions.session_config.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _noop_event_context),
    ):
        await executor.execute(run)

    client_mock.create_session.assert_awaited_once_with(
        "agent_1",
        "env_1",
        extra={
            "title": "My session",
            "metadata": {"team": "platform"},
            "vault_ids": ["vault_1"],
            "resources": [{"type": "memory_store", "memory_store_id": "ms_1"}],
        },
    )


@pytest.mark.asyncio
async def test_trigger_agent_executor_requires_config_object() -> None:
    client_mock = MagicMock()
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
        "config": "not-an-object",
    }

    with pytest.raises(ValueError, match="config must be an object"):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_trigger_agent_executor_ignores_session_create_fields_when_continuing() -> (
    None
):
    client_mock = MagicMock()
    client_mock.get_session = AsyncMock(return_value={"id": "sess_1", "status": "idle"})
    client_mock.get_session_events = _empty_session_events
    client_mock.send_user_message = AsyncMock(return_value=_user_message_event("msg_2"))
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_2"
    run.execution_properties = {
        "agentId": "agent_1",
        "sessionId": "sess_1",
        "prompt": "follow up",
        "config": {"title": "Should be ignored"},
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("actions.trigger_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _noop_event_context),
    ):
        await executor.execute(run)

    client_mock.create_session.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_agent_partition_key_is_agent_id_for_new_session() -> None:
    executor = _build_executor(TriggerAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"agentId": "agent_1"}
    assert await executor._get_partition_key(run) == "agent_1"


@pytest.mark.asyncio
async def test_trigger_agent_partition_key_is_session_id_when_continuing() -> None:
    executor = _build_executor(TriggerAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"agentId": "agent_1", "sessionId": "sess_1"}
    assert await executor._get_partition_key(run) == "sess_1"


@pytest.mark.asyncio
async def test_trigger_agent_continues_idle_session() -> None:
    client_mock = MagicMock()
    client_mock.get_session = AsyncMock(return_value={"id": "sess_1", "status": "idle"})
    client_mock.get_session_events = _empty_session_events
    client_mock.send_user_message = AsyncMock(return_value=_user_message_event("msg_2"))
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_2"
    run.execution_properties = {
        "agentId": "agent_1",
        "sessionId": "sess_1",
        "prompt": "follow up",
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("actions.trigger_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _noop_event_context),
    ):
        await executor.execute(run)

    client_mock.create_session.assert_not_called()
    client_mock.send_user_message.assert_awaited_once_with("sess_1", "follow up")
    assert (
        mock_ocean.port_client.update_run_started.call_args.args[2]
        == "claude_session_sess_1_msg_2"
    )


async def _empty_session_events(
    _session_id: str, **kwargs: object
) -> AsyncIterator[list[object]]:
    if False:
        yield []


@pytest.mark.asyncio
async def test_trigger_agent_rejects_non_idle_session() -> None:
    client_mock = MagicMock()
    client_mock.get_session = AsyncMock(
        return_value={"id": "sess_1", "status": "running"}
    )
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.execution_properties = {
        "agentId": "agent_1",
        "sessionId": "sess_1",
        "prompt": "go",
    }

    with pytest.raises(ValueError, match="cannot be continued"):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_trigger_agent_rejects_requires_action_idle() -> None:
    from anthropic.types.beta.sessions.beta_managed_agents_session_requires_action import (
        BetaManagedAgentsSessionRequiresAction,
    )
    from anthropic.types.beta.sessions.beta_managed_agents_session_status_idle_event import (
        BetaManagedAgentsSessionStatusIdleEvent,
    )
    from datetime import datetime, timezone

    idle_event = BetaManagedAgentsSessionStatusIdleEvent(
        id="idle_1",
        type="session.status_idle",
        processed_at=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        stop_reason=BetaManagedAgentsSessionRequiresAction(
            type="requires_action", event_ids=["evt_1"]
        ),
    )

    async def _idle_events(
        _session_id: str, **kwargs: object
    ) -> AsyncIterator[list[object]]:
        yield [idle_event]

    client_mock = MagicMock()
    client_mock.get_session = AsyncMock(return_value={"id": "sess_1", "status": "idle"})
    client_mock.get_session_events = _idle_events
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.execution_properties = {
        "agentId": "agent_1",
        "sessionId": "sess_1",
        "prompt": "go",
    }

    with pytest.raises(ValueError, match="waiting for user action"):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_trigger_agent_requires_environment_for_new_session() -> None:
    executor = _build_executor(TriggerAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"agentId": "agent_1", "prompt": "go"}
    with pytest.raises(ValueError, match="environmentId"):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_normalize_session_config_injects_github_pat() -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"github_authorization_token": "ghp_test"}

    with patch("actions.session_config.ocean", mock_ocean):
        api_config = await normalize_session_config(
            {
                "resources": [
                    {"type": "github_repository", "url": "https://github.com/org/repo"}
                ]
            }
        )

    assert api_config["resources"][0]["authorization_token"] == "ghp_test"


@pytest.mark.asyncio
async def test_normalize_session_config_requires_github_pat() -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {}

    with patch("actions.session_config.ocean", mock_ocean):
        with pytest.raises(ValueError, match="github_authorization_token"):
            await normalize_session_config(
                {
                    "resources": [
                        {
                            "type": "github_repository",
                            "url": "https://github.com/org/repo",
                        }
                    ]
                }
            )


@pytest.mark.asyncio
async def test_normalize_session_config_skips_repos_with_existing_token() -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {}

    with patch("actions.session_config.ocean", mock_ocean):
        api_config = await normalize_session_config(
            {
                "resources": [
                    {
                        "type": "github_repository",
                        "url": "https://github.com/org/repo",
                        "authorization_token": "already_set",
                    }
                ]
            }
        )

    assert api_config["resources"][0]["authorization_token"] == "already_set"


@pytest.mark.asyncio
async def test_trigger_agent_executor_injects_github_pat_into_session_config() -> None:
    client_mock = MagicMock()
    client_mock.create_session = AsyncMock(return_value={"id": "sess_1"})
    client_mock.send_user_message = AsyncMock(return_value=_user_message_event())
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
        "config": {
            "resources": [
                {"type": "github_repository", "url": "https://github.com/org/repo"}
            ]
        },
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.integration_config = {"github_authorization_token": "ghp_test"}
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("actions.trigger_agent_executor.ocean", mock_ocean),
        patch("actions.session_config.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _noop_event_context),
    ):
        await executor.execute(run)

    client_mock.create_session.assert_awaited_once_with(
        "agent_1",
        "env_1",
        extra={
            "resources": [
                {
                    "type": "github_repository",
                    "url": "https://github.com/org/repo",
                    "authorization_token": "ghp_test",
                }
            ]
        },
    )


@pytest.mark.asyncio
async def test_trigger_agent_executor_completes_run_synchronously_when_report_status_false() -> (
    None
):
    client_mock = MagicMock()
    client_mock.create_session = AsyncMock(return_value={"id": "sess_1"})
    client_mock.send_user_message = AsyncMock(return_value=_user_message_event())
    executor = _build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
        "reportSessionStatus": False,
    }

    mock_ocean = _build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("actions.trigger_agent_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _noop_event_context),
    ):
        await executor.execute(run)

    mock_ocean.port_client.update_run_started.assert_awaited_once()
    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert mock_ocean.port_client.report_run_completed.call_args.args[1] is True
