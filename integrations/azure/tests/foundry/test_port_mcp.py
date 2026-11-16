from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.foundry.helpers.port_mcp import (
    PORT_MCP_SERVER_LABEL,
    attach_port_mcp_to_agent_config,
    merge_port_mcp_into_tools,
    remint_port_mcp_on_agent,
    tools_from_agent_payload,
)


def test_merge_port_mcp_adds_tool_with_bearer() -> None:
    with patch(
        "azure_integration.foundry.helpers.port_mcp.required_port_mcp_url",
        return_value="https://mcp.example/v1",
    ):
        tools = merge_port_mcp_into_tools(
            [{"type": "function", "name": "lookup"}],
            enable_port_mcp=True,
            access_token="tok",
        )
    assert tools[0] == {"type": "function", "name": "lookup"}
    assert tools[1] == {
        "type": "mcp",
        "server_label": PORT_MCP_SERVER_LABEL,
        "server_url": "https://mcp.example/v1",
        "require_approval": "never",
        "headers": {"Authorization": "Bearer tok"},
    }


def test_merge_port_mcp_removes_when_disabled() -> None:
    tools = merge_port_mcp_into_tools(
        [
            {"type": "mcp", "server_label": PORT_MCP_SERVER_LABEL, "server_url": "x"},
            {"type": "function", "name": "lookup"},
        ],
        enable_port_mcp=False,
        access_token=None,
    )
    assert tools == [{"type": "function", "name": "lookup"}]


def test_attach_port_mcp_merges_existing_tools() -> None:
    with patch(
        "azure_integration.foundry.helpers.port_mcp.required_port_mcp_url",
        return_value="https://mcp.example/v1",
    ):
        config = attach_port_mcp_to_agent_config(
            {},
            enable_port_mcp=True,
            access_token=None,
            existing_tools=[
                {"type": "function", "name": "lookup"},
                {"type": "mcp", "server_label": "github"},
            ],
        )
    labels = [
        t.get("server_label") or t.get("name") for t in config["definition"]["tools"]
    ]
    assert "lookup" in labels
    assert "github" in labels
    assert PORT_MCP_SERVER_LABEL in labels


def test_tools_from_agent_payload() -> None:
    assert tools_from_agent_payload({"definition": {"tools": [{"type": "mcp"}]}}) == [
        {"type": "mcp"}
    ]
    assert tools_from_agent_payload({}) == []
    assert tools_from_agent_payload("bad") == []


@pytest.mark.asyncio
async def test_remint_port_mcp_on_agent_patches_tools() -> None:
    client = MagicMock()
    client.build_url.return_value = "https://foundry/agents/a1"
    client.send_api_request = AsyncMock(
        side_effect=[
            {
                "definition": {
                    "tools": [
                        {
                            "type": "mcp",
                            "server_label": PORT_MCP_SERVER_LABEL,
                            "server_url": "https://mcp.old/v1",
                        }
                    ]
                }
            },
            {},
        ]
    )
    with patch(
        "azure_integration.foundry.helpers.port_mcp.required_port_mcp_url",
        return_value="https://mcp.example/v1",
    ):
        await remint_port_mcp_on_agent(
            client,
            project_endpoint="https://proj",
            agent_id="a1",
            access_token="fresh",
        )
    assert client.send_api_request.await_count == 2
    patch_body = client.send_api_request.await_args_list[1].kwargs["json_body"]
    port_tool = patch_body["definition"]["tools"][0]
    assert port_tool["headers"]["Authorization"] == "Bearer fresh"
    assert port_tool["server_url"] == "https://mcp.example/v1"
