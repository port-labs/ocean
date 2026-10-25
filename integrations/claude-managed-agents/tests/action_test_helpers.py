from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, AsyncIterator, TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

from anthropic.types.beta.beta_managed_agents_session_usage import (
    BetaManagedAgentsSessionUsage,
)
from anthropic.types.beta.sessions.beta_managed_agents_text_block import (
    BetaManagedAgentsTextBlock,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_interrupt_event import (
    BetaManagedAgentsUserInterruptEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)
from actions.abstract_executor import AbstractAnthropicExecutor
from actions.port_mcp_utils import PORT_MCP_SERVER_NAME
from clients.anthropic_client import RateLimitInfo
from port_ocean.config.settings import PortSettings
from port_ocean.core.models import WorkflowNodeRun
from port_ocean.tests.helpers.aes_gcm import encrypt_aes256_gcm

T = TypeVar("T", bound=AbstractAnthropicExecutor)

_PORT_MCP_ORG_SECRET = "x" * 32


@asynccontextmanager
async def mock_event_context(*args: Any, **kwargs: Any) -> AsyncIterator[None]:
    yield


def build_executor(executor_cls: type[T], client_mock: MagicMock) -> T:
    with patch(
        "actions.abstract_executor.create_anthropic_client", return_value=client_mock
    ):
        return executor_cls()


def port_settings(**kwargs: Any) -> PortSettings:
    return PortSettings(
        client_id="id",
        client_secret=kwargs.pop("client_secret", "secret"),
        base_url="https://api.getport.io",
        **kwargs,
    )


def build_mock_ocean() -> MagicMock:
    mock_ocean = MagicMock()
    mock_ocean.config.port = port_settings()
    mock_ocean.register_raw = AsyncMock()
    mock_ocean.unregister_raw = AsyncMock()
    mock_ocean.integration.port_app_config_handler.get_port_app_config = AsyncMock()
    mock_ocean.port_client.post_run_log = AsyncMock()
    return mock_ocean


def sdk_session(
    *,
    session_id: str = "sess_1",
    status: str = "idle",
    usage: BetaManagedAgentsSessionUsage | None = None,
    metadata: dict[str, Any] | None = None,
    vault_ids: list[str] | None = None,
) -> MagicMock:
    session = MagicMock()
    session.id = session_id
    session.status = status
    session.usage = usage
    session.metadata = metadata
    session.vault_ids = vault_ids or []
    session.to_dict = MagicMock(return_value={"id": session_id, "status": status})
    return session


def sdk_agent(
    *,
    agent_id: str = "agent_1",
    version: int | None = None,
    metadata: dict[str, Any] | None = None,
    mcp_servers: list[dict[str, Any]] | None = None,
) -> MagicMock:
    agent = MagicMock()
    agent.id = agent_id
    agent.version = version
    agent.metadata = metadata
    agent.mcp_servers = mcp_servers
    agent.to_dict = MagicMock(return_value={"id": agent_id})
    return agent


def port_mcp_agent(**kwargs: Any) -> MagicMock:
    return sdk_agent(
        mcp_servers=[
            {
                "type": "url",
                "name": PORT_MCP_SERVER_NAME,
                "url": "https://mcp.getport.io/v1",
            }
        ],
        **kwargs,
    )


async def empty_vault_pages(*_args: Any, **_kwargs: Any) -> AsyncIterator[list[Any]]:
    if False:
        yield []


def sdk_environment(*, environment_id: str = "env_1") -> MagicMock:
    env = MagicMock()
    env.id = environment_id
    env.to_dict = MagicMock(return_value={"id": environment_id})
    return env


def rate_limit_client_mock(
    *,
    create: RateLimitInfo | None = None,
    read: RateLimitInfo | None = None,
) -> MagicMock:
    client_mock = MagicMock()
    client_mock.get_create_rate_limit_status.return_value = create
    client_mock.get_read_rate_limit_status.return_value = read
    return client_mock


def workflow_run_with_port_mcp(
    *,
    token: str = "tok_abc",
    identity: Any = None,
    execution_properties: dict[str, Any] | None = None,
) -> MagicMock:
    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.action_type = "trigger_agent"
    run.port_access_token = encrypt_aes256_gcm(_PORT_MCP_ORG_SECRET, token)
    run.execution_identity = identity or SimpleNamespace(
        type="actor",
        identifier="user@example.com",
    )
    run.execution_properties = execution_properties or {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
        "reportSessionStatus": True,
    }
    run.output = {}
    return run


def mock_ocean_with_client_secret() -> MagicMock:
    mock_ocean = build_mock_ocean()
    mock_ocean.config.port = port_settings(client_secret=_PORT_MCP_ORG_SECRET)
    return mock_ocean


def user_message_event(event_id: str = "msg_1") -> BetaManagedAgentsUserMessageEvent:
    return BetaManagedAgentsUserMessageEvent(
        id=event_id,
        type="user.message",
        content=[BetaManagedAgentsTextBlock(type="text", text="go")],
    )


async def empty_session_events(
    _session_id: str, **kwargs: object
) -> AsyncIterator[list[object]]:
    if False:
        yield []


def interrupt_event(event_id: str = "int_1") -> BetaManagedAgentsUserInterruptEvent:
    return BetaManagedAgentsUserInterruptEvent(
        id=event_id,
        type="user.interrupt",
    )


def cancel_run(**overrides: Any) -> MagicMock:
    run = MagicMock()
    run.id = "run_1"
    props: dict[str, Any] = {"sessionId": "sess_1"}
    props.update(overrides)
    run.execution_properties = props
    return run


def update_agent_run(**overrides: Any) -> MagicMock:
    run = MagicMock()
    run.id = "run_1"
    props: dict[str, Any] = {"agentId": "agent_1", "name": "new-name"}
    props.update(overrides)
    run.execution_properties = props
    return run


def update_env_run(**overrides: Any) -> MagicMock:
    run = MagicMock()
    run.id = "run_1"
    props: dict[str, Any] = {"environmentId": "env_1", "name": "new-name"}
    props.update(overrides)
    run.execution_properties = props
    return run
