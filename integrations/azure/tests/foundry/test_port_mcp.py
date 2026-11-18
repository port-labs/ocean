from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.foundry.helpers.port_mcp import (
    GITHUB_MCP_SERVER_LABEL,
    GITHUB_MCP_URL,
    PORT_MCP_SERVER_LABEL,
    TOOLBOX_SERVER_LABEL,
    agent_definition_kind,
    attach_toolbox_to_agent_config,
    ensure_port_mcp,
    merge_toolbox_into_tools,
    port_toolbox_name,
    port_connection_name,
    resolve_toolbox_name,
    sanitize_git_provider,
    tools_from_agent_payload,
    toolbox_consumer_url,
)


def test_resource_names_are_stable_and_short() -> None:
    agent_id = "agent-framework-agent-basic-responses"
    assert len(port_connection_name(agent_id)) <= 33
    assert len(port_toolbox_name(agent_id)) <= 33
    assert port_connection_name(agent_id) == port_connection_name(agent_id)
    assert resolve_toolbox_name(agent_id) == port_toolbox_name(agent_id)
    assert resolve_toolbox_name(agent_id, " my-toolbox ") == "my-toolbox"
    assert agent_definition_kind({"definition": {"kind": "hosted"}}) == "hosted"
    assert agent_definition_kind({}) == "prompt"


def test_merge_toolbox_adds_and_strips_legacy_port() -> None:
    tools = merge_toolbox_into_tools(
        [
            {"type": "function", "name": "lookup"},
            {
                "type": "mcp",
                "server_label": PORT_MCP_SERVER_LABEL,
                "server_url": "https://old",
                "headers": {"Authorization": "Bearer x"},
            },
        ],
        toolbox_url="https://proj/toolboxes/tb/versions/1/mcp?api-version=v1",
    )
    assert tools[0] == {"type": "function", "name": "lookup"}
    assert tools[1]["server_label"] == TOOLBOX_SERVER_LABEL
    assert "headers" not in tools[1]


def test_merge_toolbox_removes_when_disabled() -> None:
    tools = merge_toolbox_into_tools(
        [
            {
                "type": "mcp",
                "server_label": TOOLBOX_SERVER_LABEL,
                "server_url": "x",
            },
            {"type": "function", "name": "lookup"},
        ],
        toolbox_url=None,
    )
    assert tools == [{"type": "function", "name": "lookup"}]


def test_attach_toolbox_to_agent_config() -> None:
    config = attach_toolbox_to_agent_config(
        {},
        toolbox_url="https://proj/toolboxes/tb/versions/1/mcp?api-version=v1",
        existing_tools=[{"type": "mcp", "server_label": "github"}],
    )
    labels = [
        t.get("server_label")
        for t in config["definition"]["tools"]
        if isinstance(t, dict)
    ]
    assert "github" in labels
    assert TOOLBOX_SERVER_LABEL in labels


def test_tools_from_agent_payload() -> None:
    assert tools_from_agent_payload({"definition": {"tools": [{"type": "mcp"}]}}) == [
        {"type": "mcp"}
    ]
    assert tools_from_agent_payload({}) == []
    assert tools_from_agent_payload("bad") == []


def test_sanitize_git_provider() -> None:
    assert sanitize_git_provider(None) == "github"
    assert sanitize_git_provider("GitHub") == "github"
    with pytest.raises(ValueError, match="Unsupported gitProvider"):
        sanitize_git_provider("gitlab")


def test_toolbox_consumer_url() -> None:
    assert (
        toolbox_consumer_url("https://x/api/projects/p", "port-mcps-abc", version=2)
        == "https://x/api/projects/p/toolboxes/port-mcps-abc/versions/2/mcp?api-version=v1"
    )


@pytest.mark.asyncio
async def test_ensure_port_mcp_upserts_port_and_github() -> None:
    client = MagicMock()
    client.build_url.side_effect = lambda ep, path: f"{ep}/{path}"
    client.send_api_request = AsyncMock(
        side_effect=[
            {"definition": {"kind": "prompt", "tools": []}},  # GET agent
            {"version": "3"},  # toolbox POST
            {},  # POST agent tools
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
            git_provider="github",
        )
    assert result == (port_toolbox_name("cursor-test-agent"), "3")
    assert client.send_api_request.await_count == 3
    assert conn.await_count == 2
    assert conn.await_args_list[0].kwargs == {
        "project_endpoint": "https://proj",
        "name": port_connection_name("cursor-test-agent"),
        "target": "https://mcp.example/v1",
        "access_token": "port-tok",
        "project_arm_id": None,
    }
    assert conn.await_args_list[1].kwargs["target"] == GITHUB_MCP_URL
    assert conn.await_args_list[1].kwargs["access_token"] == "ghp_x"

    toolbox_post = client.send_api_request.await_args_list[1]
    tools = toolbox_post.kwargs["json_body"]["tools"]
    assert {t["server_label"] for t in tools} == {
        PORT_MCP_SERVER_LABEL,
        GITHUB_MCP_SERVER_LABEL,
    }

    agent_post = client.send_api_request.await_args_list[2]
    assert agent_post.kwargs["method"] == "POST"
    port_mcps = agent_post.kwargs["json_body"]["definition"]["tools"][0]
    assert port_mcps["server_label"] == TOOLBOX_SERVER_LABEL
    assert "/versions/3/mcp" in port_mcps["server_url"]


@pytest.mark.asyncio
async def test_ensure_port_mcp_skips_attach_for_hosted() -> None:
    client = MagicMock()
    client.build_url.side_effect = lambda ep, path: f"{ep}/{path}"
    client.send_api_request = AsyncMock(
        side_effect=[
            {"definition": {"kind": "hosted", "tools": []}},  # GET agent
            {"version": "1"},  # toolbox
        ]
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
        result = await ensure_port_mcp(
            client,
            project_endpoint="https://proj",
            agent_id="hosted-1",
            enable_port_mcp=True,
            port_access_token="tok",
            toolbox_name="team-toolbox",
        )
    assert result == ("team-toolbox", "1")
    assert client.send_api_request.await_count == 2
    toolbox_url = client.send_api_request.await_args_list[1].args[0]
    assert toolbox_url.endswith("toolboxes/team-toolbox/versions")


@pytest.mark.asyncio
async def test_ensure_port_mcp_github_only() -> None:
    client = MagicMock()
    client.build_url.side_effect = lambda ep, path: f"{ep}/{path}"
    client.send_api_request = AsyncMock(
        side_effect=[
            {"definition": {"kind": "prompt", "tools": []}},  # GET agent
            {"version": "1"},  # toolbox POST
        ]
    )
    conn = AsyncMock()
    with patch(
        "azure_integration.foundry.helpers.port_mcp.upsert_custom_keys_connection",
        conn,
    ):
        result = await ensure_port_mcp(
            client,
            project_endpoint="https://proj",
            agent_id="a1",
            enable_port_mcp=False,
            port_access_token=None,
            git_access_token="ghp_x",
            attach_to_prompt_agent=False,
        )
    assert result == (port_toolbox_name("a1"), "1")
    assert conn.await_count == 1
    toolbox_tools = client.send_api_request.await_args_list[1].kwargs["json_body"][
        "tools"
    ]
    assert len(toolbox_tools) == 1
    assert toolbox_tools[0]["server_label"] == GITHUB_MCP_SERVER_LABEL


@pytest.mark.asyncio
async def test_ensure_port_mcp_empty_tools_does_not_strip_agent() -> None:
    client = MagicMock()
    client.build_url.side_effect = lambda ep, path: f"{ep}/{path}"
    client.send_api_request = AsyncMock()
    existing = [
        {
            "type": "mcp",
            "server_label": TOOLBOX_SERVER_LABEL,
            "server_url": "https://old/versions/1/mcp",
        }
    ]
    with patch(
        "azure_integration.foundry.helpers.port_mcp.required_port_mcp_url",
        return_value="https://mcp.example/v1",
    ):
        result = await ensure_port_mcp(
            client,
            project_endpoint="https://proj",
            agent_id="agent-1",
            enable_port_mcp=True,
            port_access_token=None,
            existing_tools=existing,
        )
    assert result is None
    client.send_api_request.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_port_mcp_preserves_port_on_git_remint_without_token() -> None:
    client = MagicMock()
    client.build_url.side_effect = lambda ep, path: f"{ep}/{path}"
    client.send_api_request = AsyncMock(
        side_effect=[
            {
                "definition": {
                    "kind": "prompt",
                    "tools": [
                        {
                            "type": "mcp",
                            "server_label": TOOLBOX_SERVER_LABEL,
                            "server_url": "https://old/versions/1/mcp",
                        }
                    ],
                }
            },
            {"version": "2"},  # toolbox POST
            {},  # POST agent tools
        ]
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
        result = await ensure_port_mcp(
            client,
            project_endpoint="https://proj",
            agent_id="agent-1",
            enable_port_mcp=True,
            port_access_token=None,
            git_access_token="ghp_x",
        )
    assert result is not None
    toolbox_tools = client.send_api_request.await_args_list[1].kwargs["json_body"][
        "tools"
    ]
    assert {t["server_label"] for t in toolbox_tools} == {
        GITHUB_MCP_SERVER_LABEL,
        PORT_MCP_SERVER_LABEL,
    }


@pytest.mark.asyncio
async def test_ensure_port_mcp_passes_project_arm_id_to_connection_upsert() -> None:
    client = MagicMock()
    client.build_url.side_effect = lambda ep, path: f"{ep}/{path}"
    client.send_api_request = AsyncMock(
        side_effect=[
            {"definition": {"kind": "hosted", "tools": []}},
            {"version": "1"},
        ]
    )
    conn = AsyncMock()
    arm_id = (
        "/subscriptions/s/resourceGroups/rg/providers/"
        "Microsoft.CognitiveServices/accounts/acct/projects/p"
    )
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
        await ensure_port_mcp(
            client,
            project_endpoint="https://proj",
            agent_id="a1",
            enable_port_mcp=True,
            port_access_token="port_tok",
            attach_to_prompt_agent=False,
            project_arm_id=arm_id,
        )
    assert conn.await_args.kwargs["project_arm_id"] == arm_id
