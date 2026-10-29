from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from actions.port_mcp_utils import (
    PORT_MCP_SERVER_NAME,
    PortMcpBinding,
    _is_vault_credential_url_matching,
    attach_port_mcp_settings_to_agent_config,
    ensure_port_mcp_binding,
    is_agent_configured_with_port_mcp,
)


from tests.action_test_helpers import (
    empty_vault_pages,
    mock_ocean_with_client_secret,
    workflow_run_with_port_mcp,
)


def test_port_mcp_urls_keep_getport_and_port_hosts_distinct() -> None:
    from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
        BetaManagedAgentsMCPServerURLDefinition,
    )
    from anthropic.types.beta.vaults.beta_managed_agents_static_bearer_auth_response import (
        BetaManagedAgentsStaticBearerAuthResponse,
    )

    getport = "https://mcp.getport.io/v1"
    port = "https://mcp.port.io/v1"
    servers = [
        BetaManagedAgentsMCPServerURLDefinition(
            type="url", name=PORT_MCP_SERVER_NAME, url=getport
        )
    ]
    credential = SimpleNamespace(
        auth=BetaManagedAgentsStaticBearerAuthResponse(
            type="static_bearer", mcp_server_url=getport
        )
    )

    with patch(
        "actions.port_mcp_utils.ocean",
        SimpleNamespace(config=SimpleNamespace(port=SimpleNamespace(mcp_url=port))),
    ):
        assert not is_agent_configured_with_port_mcp(servers)
    assert _is_vault_credential_url_matching(credential, getport)
    assert not _is_vault_credential_url_matching(credential, port)


def test_apply_port_mcp_adds_server_and_toolset() -> None:
    result = attach_port_mcp_settings_to_agent_config({"description": "d"})
    assert result["description"] == "d"
    assert "metadata" not in result

    def _field(item: object, key: str) -> object:
        if isinstance(item, dict):
            return item.get(key)
        return getattr(item, key, None)

    assert any(
        _field(s, "name") == PORT_MCP_SERVER_NAME
        and _field(s, "url") == "https://mcp.getport.io/v1"
        for s in result["mcp_servers"]
    )
    assert any(
        _field(t, "type") == "mcp_toolset"
        and _field(t, "mcp_server_name") == PORT_MCP_SERVER_NAME
        for t in result["tools"]
    )


def test_apply_port_mcp_is_idempotent() -> None:
    once = attach_port_mcp_settings_to_agent_config({})
    twice = attach_port_mcp_settings_to_agent_config(once)
    assert len(twice["mcp_servers"]) == 1
    assert len(twice["tools"]) == 1


def test_apply_port_mcp_replaces_stale_port_named_server() -> None:
    from anthropic.types.beta.beta_managed_agents_always_allow_policy import (
        BetaManagedAgentsAlwaysAllowPolicy,
    )
    from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
        BetaManagedAgentsMCPServerURLDefinition,
    )
    from anthropic.types.beta.beta_managed_agents_mcp_toolset import (
        BetaManagedAgentsMCPToolset,
    )
    from anthropic.types.beta.beta_managed_agents_mcp_toolset_default_config import (
        BetaManagedAgentsMCPToolsetDefaultConfig,
    )

    stale = BetaManagedAgentsMCPServerURLDefinition(
        type="url",
        name=PORT_MCP_SERVER_NAME,
        url="https://mcp.old-region.example/v1",
    )
    stale_toolset = BetaManagedAgentsMCPToolset(
        type="mcp_toolset",
        mcp_server_name=PORT_MCP_SERVER_NAME,
        configs=[],
        default_config=BetaManagedAgentsMCPToolsetDefaultConfig(
            enabled=False,
            permission_policy=BetaManagedAgentsAlwaysAllowPolicy(type="always_allow"),
        ),
    )
    agent = MagicMock()
    agent.mcp_servers = [stale]
    agent.tools = [stale_toolset]

    result = attach_port_mcp_settings_to_agent_config({}, existing_agent=agent)

    assert len(result["mcp_servers"]) == 1
    assert getattr(result["mcp_servers"][0], "url", None) == "https://mcp.getport.io/v1"
    assert len(result["tools"]) == 1
    assert result["tools"][0]["mcp_server_name"] == PORT_MCP_SERVER_NAME
    assert result["tools"][0]["default_config"]["enabled"] is True


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
    from datetime import datetime, timezone

    from anthropic.types.beta.vaults.beta_managed_agents_credential import (
        BetaManagedAgentsCredential,
    )
    from anthropic.types.beta.vaults.beta_managed_agents_static_bearer_auth_response import (
        BetaManagedAgentsStaticBearerAuthResponse,
    )

    existing_vault = SimpleNamespace(
        id="vault_1", display_name="port-mcp-user@example.com"
    )
    existing_cred = BetaManagedAgentsCredential(
        id="cred_1",
        display_name="port-mcp",
        type="vault_credential",
        vault_id="vault_1",
        metadata={},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        auth=BetaManagedAgentsStaticBearerAuthResponse(
            type="static_bearer",
            mcp_server_url="https://mcp.getport.io/v1",
        ),
    )
    pages: Iterator[list[Any]] = iter([[existing_vault], [existing_cred]])

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
