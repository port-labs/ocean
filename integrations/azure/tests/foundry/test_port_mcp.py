from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.foundry.helpers.port_mcp import (
    GITHUB_MCP_SERVER_LABEL,
    GITHUB_MCP_URL,
    PORT_MCP_SERVER_LABEL,
    TOOLBOX_SERVER_LABEL,
    agent_definition_kind,
    ensure_port_mcp,
    merge_toolbox_into_tools,
    port_connection_name,
    port_toolbox_name,
    resolve_toolbox_name,
    sanitize_git_provider,
    toolbox_consumer_url,
)


def _client(side_effect: list[Any] | Any) -> MagicMock:
    client = MagicMock()
    client.build_url.side_effect = lambda ep, path: f"{ep}/{path}"
    client.send_api_request = AsyncMock(side_effect=side_effect)
    return client


def test_helpers() -> None:
    agent_id = "agent-framework-agent-basic-responses"
    assert len(port_connection_name(agent_id)) <= 33
    assert resolve_toolbox_name(agent_id, " my-toolbox ") == "my-toolbox"
    assert agent_definition_kind({"definition": {"kind": "hosted"}}) == "hosted"
    assert sanitize_git_provider("GitHub") == "github"
    with pytest.raises(ValueError):
        sanitize_git_provider("gitlab")
    assert "versions/2/mcp" in toolbox_consumer_url(
        "https://x/api/projects/p", "tb", version=2
    )
    tools = merge_toolbox_into_tools(
        [{"type": "mcp", "server_label": PORT_MCP_SERVER_LABEL, "server_url": "old"}],
        toolbox_url="https://proj/toolboxes/tb/versions/1/mcp",
    )
    assert tools[0]["server_label"] == TOOLBOX_SERVER_LABEL


@pytest.mark.asyncio
async def test_ensure_port_mcp_core_paths() -> None:
    client = _client(
        [
            {"definition": {"kind": "prompt", "tools": []}},
            {},
            {"version": "3"},
            {},
        ]
    )
    conn = AsyncMock()
    with (
        patch(
            "azure_integration.foundry.helpers.port_mcp.required_port_mcp_url",
            return_value="https://mcp.example/v1",
        ),
        patch(
            "azure_integration.foundry.helpers.port_mcp.upsert_custom_keys_connection",
            conn,
        ),
    ):
        result = await ensure_port_mcp(
            client,
            project_endpoint="https://proj",
            agent_id="cursor-test-agent",
            enable_port_mcp=True,
            port_access_token="port-tok",
            git_access_token="ghp_x",
        )
    assert result == (port_toolbox_name("cursor-test-agent"), "3")
    assert conn.await_count == 2
    assert conn.await_args_list[1].kwargs["target"] == GITHUB_MCP_URL
    labels = {
        t["server_label"]
        for t in client.send_api_request.await_args_list[2].kwargs["json_body"]["tools"]
    }
    assert labels == {PORT_MCP_SERVER_LABEL, GITHUB_MCP_SERVER_LABEL}

    hosted = _client(
        [{"definition": {"kind": "hosted", "tools": []}}, {}, {"version": "1"}]
    )
    with (
        patch(
            "azure_integration.foundry.helpers.port_mcp.required_port_mcp_url",
            return_value="https://mcp.example/v1",
        ),
        patch(
            "azure_integration.foundry.helpers.port_mcp.upsert_custom_keys_connection",
            AsyncMock(),
        ),
    ):
        assert await ensure_port_mcp(
            hosted,
            project_endpoint="https://proj",
            agent_id="hosted-1",
            enable_port_mcp=True,
            port_access_token="tok",
            toolbox_name="team-toolbox",
        ) == ("team-toolbox", "1")

    empty = _client([])
    assert (
        await ensure_port_mcp(
            empty,
            project_endpoint="https://proj",
            agent_id="a1",
            enable_port_mcp=True,
            port_access_token=None,
            existing_tools=[],
        )
        is None
    )

    # Token remint reuses toolbox version when tools already present
    agent_id = "reuse-agent"
    tb = port_toolbox_name(agent_id)
    port_conn = port_connection_name(agent_id)
    port_url = "https://mcp.example/v1"
    reuse = _client(
        [
            {
                "versions": {
                    "latest": {
                        "version": "7",
                        "tools": [
                            {
                                "type": "mcp",
                                "server_label": PORT_MCP_SERVER_LABEL,
                                "server_url": port_url,
                                "project_connection_id": port_conn,
                            }
                        ],
                    }
                }
            }
        ]
    )
    with (
        patch(
            "azure_integration.foundry.helpers.port_mcp.required_port_mcp_url",
            return_value=port_url,
        ),
        patch(
            "azure_integration.foundry.helpers.port_mcp.upsert_custom_keys_connection",
            AsyncMock(),
        ),
    ):
        assert await ensure_port_mcp(
            reuse,
            project_endpoint="https://proj",
            agent_id=agent_id,
            enable_port_mcp=True,
            port_access_token="fresh",
            existing_tools=[
                {
                    "type": "mcp",
                    "server_label": TOOLBOX_SERVER_LABEL,
                    "server_url": f"https://proj/toolboxes/{tb}/versions/7/mcp",
                }
            ],
            agent_kind="prompt",
        ) == (tb, "7")
    assert reuse.send_api_request.await_count == 1
