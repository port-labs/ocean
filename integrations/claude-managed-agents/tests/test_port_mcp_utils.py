from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_managed_agents.actions.mcp_vault_utils import (
    agent_has_mcp_url,
    is_vault_credential_url_matching,
)
from claude_managed_agents.actions.port_mcp_utils import (
    PORT_MCP_SERVER_NAME,
    PortMcpBinding,
    attach_port_mcp_settings_to_agent_config,
    ensure_port_mcp_credential,
    get_or_create_mcp_vault,
)


from tests.action_test_helpers import (
    empty_vault_pages,
    mock_ocean_with_client_secret,
    workflow_run_with_port_mcp,
)


def test_port_mcp_urls_keep_getport_and_port_hosts_distinct() -> None:
    from datetime import datetime, timezone

    from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
        BetaManagedAgentsMCPServerURLDefinition,
    )
    from anthropic.types.beta.vaults.beta_managed_agents_credential import (
        BetaManagedAgentsCredential,
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
    credential = BetaManagedAgentsCredential(
        id="cred_1",
        display_name="port-mcp",
        type="vault_credential",
        vault_id="vault_1",
        metadata={},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        auth=BetaManagedAgentsStaticBearerAuthResponse(
            type="static_bearer",
            mcp_server_url=getport,
        ),
    )

    with patch(
        "claude_managed_agents.actions.port_mcp_utils.ocean",
        SimpleNamespace(config=SimpleNamespace(port=SimpleNamespace(mcp_url=port))),
    ):
        assert not agent_has_mcp_url(port, servers)
    assert is_vault_credential_url_matching(credential, getport)
    assert not is_vault_credential_url_matching(credential, port)


def test_apply_port_mcp_adds_server_and_toolset() -> None:
    result, changed = attach_port_mcp_settings_to_agent_config(
        {"description": "d"},
        enable_port_mcp=True,
        virtual_mcp_server_ids=[],
    )
    assert changed is True
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
    once, _ = attach_port_mcp_settings_to_agent_config(
        {}, enable_port_mcp=True, virtual_mcp_server_ids=[]
    )
    agent = MagicMock()
    agent.mcp_servers = once["mcp_servers"]
    agent.tools = once["tools"]
    twice, changed = attach_port_mcp_settings_to_agent_config(
        {},
        existing_agent=agent,
        enable_port_mcp=True,
        virtual_mcp_server_ids=[],
    )
    assert changed is False
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

    result, _ = attach_port_mcp_settings_to_agent_config(
        {},
        existing_agent=agent,
        enable_port_mcp=True,
        virtual_mcp_server_ids=[],
    )

    assert len(result["mcp_servers"]) == 1
    assert getattr(result["mcp_servers"][0], "url", None) == "https://mcp.getport.io/v1"
    assert len(result["tools"]) == 1
    assert result["tools"][0]["mcp_server_name"] == PORT_MCP_SERVER_NAME
    assert result["tools"][0]["default_config"]["enabled"] is True


def test_apply_port_mcp_replaces_stale_virtual_mcp_named_server() -> None:
    from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
        BetaManagedAgentsMCPServerURLDefinition,
    )

    stale = BetaManagedAgentsMCPServerURLDefinition(
        type="url",
        name="port-virtual-mcp-payments",
        url="https://mcp.old-region.example/v1/virtual-server/payments",
    )
    agent = MagicMock()
    agent.mcp_servers = [stale]
    agent.tools = []

    result, changed = attach_port_mcp_settings_to_agent_config(
        {},
        existing_agent=agent,
        enable_port_mcp=False,
        virtual_mcp_server_ids=["payments"],
    )

    assert changed is True
    assert len(result["mcp_servers"]) == 1
    assert (
        getattr(result["mcp_servers"][0], "name", None) == "port-virtual-mcp-payments"
    )
    assert (
        getattr(result["mcp_servers"][0], "url", None)
        == "https://mcp.getport.io/v1/virtual-server/payments"
    )
    assert len(result["tools"]) == 1
    assert result["tools"][0]["mcp_server_name"] == "port-virtual-mcp-payments"


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
        patch("claude_managed_agents.actions.port_mcp_utils.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.port_mcp_utils.get_run_access_token",
            return_value="tok_abc",
        ),
    ):
        vault = await get_or_create_mcp_vault(client, "port-mcp-user@example.com")
        binding = await ensure_port_mcp_credential(
            client,
            workflow_run_with_port_mcp(),
            vault.id,
            "https://mcp.getport.io/v1",
        )

    assert binding == PortMcpBinding(
        mcp_server_url="https://mcp.getport.io/v1",
        vault_id="vault_new",
        credential_id="cred_new",
    )
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
        patch("claude_managed_agents.actions.port_mcp_utils.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.port_mcp_utils.get_run_access_token",
            return_value="tok_abc",
        ),
    ):
        vault = await get_or_create_mcp_vault(client, "port-mcp-user@example.com")
        binding = await ensure_port_mcp_credential(
            client,
            workflow_run_with_port_mcp(),
            vault.id,
            "https://mcp.getport.io/v1",
        )

    assert binding == PortMcpBinding(
        mcp_server_url="https://mcp.getport.io/v1",
        vault_id="vault_1",
        credential_id="cred_1",
    )
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


def test_attach_virtual_mcp_without_full_port() -> None:
    result, changed = attach_port_mcp_settings_to_agent_config(
        {},
        enable_port_mcp=False,
        virtual_mcp_server_ids=["payments"],
    )
    assert changed is True
    assert len(result["mcp_servers"]) == 1
    assert (
        getattr(result["mcp_servers"][0], "name", None) == "port-virtual-mcp-payments"
    )
    assert (
        getattr(result["mcp_servers"][0], "url", None)
        == "https://mcp.getport.io/v1/virtual-server/payments"
    )


def test_attach_replace_swaps_virtual_set_keeps_other_mcp() -> None:
    from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
        BetaManagedAgentsMCPServerURLDefinition,
    )

    keep_tool = MagicMock()
    keep_tool.type = "other"
    keep_tool.mcp_server_name = "other"
    old_virtual_tool = MagicMock()
    old_virtual_tool.type = "mcp_toolset"
    old_virtual_tool.mcp_server_name = "port-virtual-mcp-old"
    port_tool = MagicMock()
    port_tool.type = "mcp_toolset"
    port_tool.mcp_server_name = PORT_MCP_SERVER_NAME

    agent = MagicMock()
    agent.mcp_servers = [
        BetaManagedAgentsMCPServerURLDefinition(
            type="url", name="other", url="https://example.com"
        ),
        BetaManagedAgentsMCPServerURLDefinition(
            type="url",
            name="port-virtual-mcp-old",
            url="https://mcp.getport.io/v1/virtual-server/old",
        ),
        BetaManagedAgentsMCPServerURLDefinition(
            type="url",
            name=PORT_MCP_SERVER_NAME,
            url="https://mcp.getport.io/v1",
        ),
    ]
    agent.tools = [keep_tool, old_virtual_tool, port_tool]

    result, _ = attach_port_mcp_settings_to_agent_config(
        {},
        existing_agent=agent,
        enable_port_mcp=False,
        virtual_mcp_server_ids=["payments"],
        replace=True,
    )

    names = {getattr(s, "name", None) for s in result["mcp_servers"]}
    assert names == {"other", "port-virtual-mcp-payments"}
    assert keep_tool in result["tools"]
    assert old_virtual_tool not in result["tools"]
    assert port_tool not in result["tools"]


@pytest.mark.asyncio
async def test_ensure_port_mcp_binding_creates_virtual_credentials() -> None:
    client = MagicMock()
    client.paginate = empty_vault_pages
    client.beta.vaults.create = AsyncMock(
        return_value=SimpleNamespace(id="vault_new", display_name="vault")
    )
    client.beta.vaults.credentials.create = AsyncMock(
        side_effect=[
            SimpleNamespace(id="cred_port"),
            SimpleNamespace(id="cred_virtual"),
        ]
    )
    client.beta.vaults.credentials.update = AsyncMock()
    mock_ocean = mock_ocean_with_client_secret()

    with (
        patch("claude_managed_agents.actions.port_mcp_utils.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.port_mcp_utils.get_run_access_token",
            return_value="tok_abc",
        ),
    ):
        vault = await get_or_create_mcp_vault(client, "vault")
        bindings = [
            await ensure_port_mcp_credential(
                client,
                workflow_run_with_port_mcp(),
                vault.id,
                url,
            )
            for url in [
                "https://mcp.getport.io/v1",
                "https://mcp.getport.io/v1/virtual-server/payments",
            ]
        ]

    assert bindings == [
        PortMcpBinding(
            mcp_server_url="https://mcp.getport.io/v1",
            vault_id="vault_new",
            credential_id="cred_port",
        ),
        PortMcpBinding(
            mcp_server_url="https://mcp.getport.io/v1/virtual-server/payments",
            vault_id="vault_new",
            credential_id="cred_virtual",
        ),
    ]
    assert client.beta.vaults.credentials.create.await_count == 2
