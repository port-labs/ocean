from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, AsyncIterator, Iterator, TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.config.settings import PortSettings

from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_text_block import (
    BetaManagedAgentsTextBlock,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_interrupt_event import (
    BetaManagedAgentsUserInterruptEvent,
)
from actions.abstract_executor import AbstractAnthropicExecutor
from actions.archive_agent_executor import (
    AGENT_ARCHIVED_STATUS_LABEL,
    ArchiveAgentExecutor,
)
from actions.cancel_session_executor import (
    SESSION_CANCELLED_STATUS_LABEL,
    SESSION_NOT_CANCELLABLE_STATUS_LABEL,
    CancelSessionExecutor,
)
from actions.create_agent_executor import (
    AGENT_CREATED_STATUS_LABEL,
    CreateAgentExecutor,
)
from actions.create_environment_executor import (
    ENVIRONMENT_CREATED_STATUS_LABEL,
    CreateEnvironmentExecutor,
)
from actions.delete_environment_executor import (
    ENVIRONMENT_DELETED_STATUS_LABEL,
    DeleteEnvironmentExecutor,
)
from actions.exceptions import InvalidActionParametersException
from actions.trigger_agent_executor import (
    PORT_IDENTITY_ID_KEY,
    SESSION_NOT_CONTINUABLE_STATUS_LABEL,
    TriggerAgentExecutor,
)
from actions.update_agent_executor import (
    AGENT_UPDATED_STATUS_LABEL,
    UpdateAgentExecutor,
)
from actions.update_environment_executor import (
    ENVIRONMENT_UPDATED_STATUS_LABEL,
    UpdateEnvironmentExecutor,
)
from actions.types import TriggerAgentSessionOutput, list_cost_to_usd
from actions.port_mcp_utils import (
    PORT_MCP_SERVER_NAME,
    PortMcpBinding,
    attach_port_mcp_settings_to_agent_config,
    ensure_port_mcp_binding,
)
from actions.utils import (
    build_external_id,
    build_session_link,
    normalize_session_config,
)
from anthropic.types.beta.beta_managed_agents_session_usage import (
    BetaManagedAgentsSessionUsage,
)
from clients.anthropic_client import RateLimitInfo
from port_ocean.core.models import ActionRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.tests.helpers.aes_gcm import encrypt_aes256_gcm

T = TypeVar("T", bound=AbstractAnthropicExecutor)

from tests.action_test_helpers import (
    empty_vault_pages,
    mock_ocean_with_client_secret,
    workflow_run_with_port_mcp,
)

def test_apply_port_mcp_adds_server_and_toolset() -> None:
    result = attach_port_mcp_settings_to_agent_config({"description": "d"})
    assert result["description"] == "d"
    assert "metadata" not in result
    assert any(
        s.get("name") == PORT_MCP_SERVER_NAME
        and s.get("url") == "https://mcp.getport.io/v1"
        for s in result["mcp_servers"]
    )
    assert any(
        t.get("type") == "mcp_toolset"
        and t.get("mcp_server_name") == PORT_MCP_SERVER_NAME
        for t in result["tools"]
    )

def test_apply_port_mcp_is_idempotent() -> None:
    once = attach_port_mcp_settings_to_agent_config({})
    twice = attach_port_mcp_settings_to_agent_config(once)
    assert len(twice["mcp_servers"]) == 1
    assert len(twice["tools"]) == 1

@pytest.mark.asyncio
async def test_ensure_port_mcp_binding_creates_vault_and_credential() -> None:
    client = MagicMock()
    client.paginate = empty_vault_pages
    client.beta.vaults.create = AsyncMock(
        return_value=SimpleNamespace(
            id="vault_new", display_name="port-mcp-user@example.com"
        )
    )
    client.beta.vaults.credentials.create = AsyncMock(
        return_value=SimpleNamespace(id="cred_new")
    )
    client.beta.vaults.credentials.update = AsyncMock()
    mock_ocean = mock_ocean_with_client_secret()

    with (
        patch("actions.port_mcp_utils.ocean", mock_ocean),
        patch("actions.port_mcp_utils.get_run_access_token", return_value="tok_abc"),
    ):
        binding = await ensure_port_mcp_binding(
            client,
            workflow_run_with_port_mcp(),
            vault_name="port-mcp-user@example.com",
        )

    assert binding == PortMcpBinding(vault_id="vault_new", credential_id="cred_new")
    assert (
        client.beta.vaults.create.await_args.kwargs["display_name"]
        == "port-mcp-user@example.com"
    )
    auth = client.beta.vaults.credentials.create.await_args.kwargs["auth"]
    assert auth == {
        "type": "static_bearer",
        "token": "tok_abc",
        "mcp_server_url": "https://mcp.getport.io/v1",
    }
    client.beta.vaults.credentials.update.assert_not_awaited()

@pytest.mark.asyncio
async def test_ensure_port_mcp_binding_updates_existing_credential() -> None:
    existing_vault = SimpleNamespace(
        id="vault_1", display_name="port-mcp-user@example.com"
    )
    existing_cred = SimpleNamespace(
        id="cred_1",
        display_name="port-mcp",
        archived_at=None,
        auth=SimpleNamespace(
            type="static_bearer",
            mcp_server_url="https://mcp.getport.io/v1",
        ),
    )
    pages = iter([[existing_vault], [existing_cred]])

    async def _paginate(*_a: Any, **_k: Any) -> AsyncIterator[list[Any]]:
        yield next(pages)

    client = MagicMock()
    client.paginate = _paginate
    client.beta.vaults.create = AsyncMock()
    client.beta.vaults.credentials.create = AsyncMock()
    client.beta.vaults.credentials.update = AsyncMock()
    mock_ocean = mock_ocean_with_client_secret()

    with (
        patch("actions.port_mcp_utils.ocean", mock_ocean),
        patch("actions.port_mcp_utils.get_run_access_token", return_value="tok_abc"),
    ):
        binding = await ensure_port_mcp_binding(
            client,
            workflow_run_with_port_mcp(),
            vault_name="port-mcp-user@example.com",
        )

    assert binding == PortMcpBinding(vault_id="vault_1", credential_id="cred_1")
    client.beta.vaults.create.assert_not_awaited()
    client.beta.vaults.credentials.create.assert_not_awaited()
    client.beta.vaults.credentials.update.assert_awaited_once_with(
        "cred_1",
        vault_id="vault_1",
        auth={
            "type": "static_bearer",
            "token": "tok_abc",
        },
    )
