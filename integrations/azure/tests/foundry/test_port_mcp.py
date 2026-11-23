from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.foundry.clients.http.foundry_client import FoundryApiError
from azure_integration.foundry.helpers.port_mcp import (
    GITHUB_MCP_URL,
    agent_definition_kind,
    ensure_port_mcp,
    port_connection_name,
    port_toolbox_name,
    sanitize_git_provider,
)
from azure_integration.foundry.helpers.toolbox import (
    merge_toolbox_into_tools,
    toolbox_name_from_agent_tools,
)
from azure_integration.foundry.models.toolbox import (
    GITHUB_MCP_SERVER_LABEL,
    PORT_MCP_SERVER_LABEL,
    TOOLBOX_SERVER_LABEL,
)


def _client(side_effect: list[Any] | Any) -> MagicMock:
    client = MagicMock()
    client.build_url.side_effect = lambda ep, path: f"{ep}/{path}"
    client.send_api_request = AsyncMock(side_effect=side_effect)
    return client


def _foreign_tools(tb: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "mcp",
            "server_label": "other",
            "server_url": f"https://proj/toolboxes/{tb}/versions/7/mcp",
        }
    ]


def test_helpers() -> None:
    agent_id = "agent-framework-agent-basic-responses"
    assert len(port_connection_name(agent_id)) <= 33
    assert port_toolbox_name(agent_id).startswith("port-mcps-")
    assert (
        agent_definition_kind(
            {"versions": {"latest": {"definition": {"kind": "hosted"}}}}
        )
        == "hosted"
    )
    assert sanitize_git_provider("GitHub") == "github"
    with pytest.raises(ValueError):
        sanitize_git_provider("gitlab")
    tools = merge_toolbox_into_tools(
        [{"type": "mcp", "server_label": PORT_MCP_SERVER_LABEL, "server_url": "old"}],
        toolbox_url="https://proj/toolboxes/tb/versions/1/mcp",
    )
    assert tools[0]["server_label"] == TOOLBOX_SERVER_LABEL
    assert (
        toolbox_name_from_agent_tools(
            [
                {
                    "type": "mcp",
                    "server_label": "foreign",
                    "server_url": "https://proj/toolboxes/team-box/versions/1/mcp",
                }
            ]
        )
        == "team-box"
    )


@pytest.mark.asyncio
async def test_ensure_port_mcp_core_paths() -> None:
    client = _client(
        [
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
            existing_agent={
                "versions": {
                    "latest": {
                        "definition": {
                            "kind": "prompt",
                            "model": "gpt-4o",
                            "tools": [],
                        }
                    }
                }
            },
            existing_tools=[],
            agent_kind="prompt",
        )
    assert result == (port_toolbox_name("cursor-test-agent"), "3")
    assert conn.await_count == 2
    assert conn.await_args_list[1].kwargs["target"] == GITHUB_MCP_URL
    labels = {
        t["server_label"]
        for t in client.send_api_request.await_args_list[1].kwargs["json_body"]["tools"]
    }
    assert labels == {PORT_MCP_SERVER_LABEL, GITHUB_MCP_SERVER_LABEL}
    attach_body = client.send_api_request.await_args_list[2].kwargs["json_body"]
    assert attach_body["definition"]["model"] == "gpt-4o"

    hosted = _client([{}, {"version": "1"}])
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
            existing_tools=[],
            agent_kind="hosted",
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


@pytest.mark.asyncio
async def test_prompt_foreign_toolbox_skips_without_opt_in() -> None:
    agent_id = "reuse-agent"
    tb = "foreign-box"
    conn = AsyncMock()
    run = MagicMock()
    post_run_log = AsyncMock()
    with (
        patch(
            "azure_integration.foundry.helpers.port_mcp.required_port_mcp_url",
            return_value="https://mcp.example/v1",
        ),
        patch(
            "azure_integration.foundry.helpers.port_mcp.upsert_custom_keys_connection",
            conn,
        ),
        patch(
            "azure_integration.foundry.helpers.port_mcp.ocean.port_client.post_run_log",
            post_run_log,
        ),
    ):
        assert (
            await ensure_port_mcp(
                _client([]),
                project_endpoint="https://proj",
                agent_id=agent_id,
                enable_port_mcp=True,
                port_access_token="fresh",
                existing_tools=_foreign_tools(tb),
                agent_kind="prompt",
                use_existing_toolbox=False,
                run=run,
            )
            is None
        )
    conn.assert_not_awaited()
    post_run_log.assert_awaited_once()
    assert post_run_log.await_args is not None
    assert post_run_log.await_args.args[0] is run
    assert tb in post_run_log.await_args.args[1]
    assert post_run_log.await_args.kwargs["level"] == "WARNING"


@pytest.mark.asyncio
async def test_prompt_foreign_toolbox_merges_when_opt_in() -> None:
    agent_id = "reuse-agent"
    tb = "foreign-box"
    port_url = "https://mcp.example/v1"
    reuse = _client(
        [
            {
                "versions": {
                    "latest": {
                        "version": "7",
                        "tools": [
                            {"type": "web_search"},
                            {
                                "type": "mcp",
                                "server_label": PORT_MCP_SERVER_LABEL,
                                "server_url": port_url,
                                "project_connection_id": port_connection_name(agent_id),
                            },
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
            existing_tools=_foreign_tools(tb),
            agent_kind="prompt",
            use_existing_toolbox=True,
        ) == (tb, "7")
    assert reuse.send_api_request.await_count == 1


@pytest.mark.asyncio
async def test_existing_generated_toolbox_reuses_without_opt_in() -> None:
    agent_id = "cursor-test-agent"
    tb = port_toolbox_name(agent_id)
    port_url = "https://mcp.example/v1"
    reuse = _client(
        [
            {
                "versions": {
                    "latest": {
                        "version": "2",
                        "tools": [
                            {
                                "type": "mcp",
                                "server_label": PORT_MCP_SERVER_LABEL,
                                "server_url": port_url,
                                "project_connection_id": port_connection_name(agent_id),
                            },
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
                    "server_url": f"https://proj/toolboxes/{tb}/versions/2/mcp",
                }
            ],
            agent_kind="prompt",
            use_existing_toolbox=False,
        ) == (tb, "2")
    # Same version already pinned → GET toolbox only, no agent POST.
    assert reuse.send_api_request.await_count == 1


@pytest.mark.asyncio
async def test_prompt_reattaches_when_toolbox_version_bumps() -> None:
    agent_id = "cursor-test-agent"
    tb = port_toolbox_name(agent_id)
    port_url = "https://mcp.example/v1"
    client = _client(
        [
            {
                "versions": {
                    "latest": {
                        "version": "2",
                        "tools": [
                            {
                                "type": "mcp",
                                "server_label": PORT_MCP_SERVER_LABEL,
                                "server_url": port_url,
                                "project_connection_id": port_connection_name(agent_id),
                            },
                        ],
                    }
                }
            },
            {"version": "3"},
            {},
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
            client,
            project_endpoint="https://proj",
            agent_id=agent_id,
            enable_port_mcp=True,
            port_access_token="fresh",
            git_access_token="ghp_x",
            existing_agent={
                "versions": {
                    "latest": {
                        "definition": {
                            "kind": "prompt",
                            "model": "gpt-4o",
                            "tools": [],
                        }
                    }
                }
            },
            existing_tools=[
                {
                    "type": "mcp",
                    "server_label": TOOLBOX_SERVER_LABEL,
                    "server_url": f"https://proj/toolboxes/{tb}/versions/2/mcp",
                }
            ],
            agent_kind="prompt",
        ) == (tb, "3")
    attach_url = client.send_api_request.await_args_list[2].kwargs["json_body"][
        "definition"
    ]["tools"][-1]["server_url"]
    assert f"/toolboxes/{tb}/versions/3/" in attach_url


@pytest.mark.asyncio
async def test_prompt_ignores_toolbox_name_for_foreign() -> None:
    """Prompt path ignores toolboxName; without opt-in, skip even if name matches."""
    agent_id = "reuse-agent"
    tb = "foreign-box"
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
        assert (
            await ensure_port_mcp(
                _client([]),
                project_endpoint="https://proj",
                agent_id=agent_id,
                enable_port_mcp=True,
                port_access_token="fresh",
                toolbox_name=tb,
                existing_tools=_foreign_tools(tb),
                agent_kind="prompt",
                use_existing_toolbox=False,
            )
            is None
        )
    conn.assert_not_awaited()


@pytest.mark.asyncio
async def test_hosted_toolbox_name_must_exist() -> None:
    agent_id = "hosted-1"
    client = _client([FoundryApiError("missing", status_code=404)])
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
        with pytest.raises(ValueError, match="was not found"):
            await ensure_port_mcp(
                client,
                project_endpoint="https://proj",
                agent_id=agent_id,
                enable_port_mcp=True,
                port_access_token="tok",
                toolbox_name="missing-box",
                existing_tools=[],
                agent_kind="hosted",
            )


@pytest.mark.asyncio
async def test_hosted_without_toolbox_name_creates_port_owned() -> None:
    agent_id = "hosted-1"
    client = _client([{}, {"version": "1"}])
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
            client,
            project_endpoint="https://proj",
            agent_id=agent_id,
            enable_port_mcp=True,
            port_access_token="tok",
            existing_tools=[],
            agent_kind="hosted",
        ) == (port_toolbox_name(agent_id), "1")
    # GET missing + POST version; no agent attach for hosted
    assert client.send_api_request.await_count == 2


@pytest.mark.asyncio
async def test_existing_toolbox_posts_merged_version() -> None:
    agent_id = "merge-agent"
    tb = "team-box"
    port_conn = port_connection_name(agent_id)
    port_url = "https://mcp.example/v1"
    client = _client(
        [
            {
                "versions": {
                    "latest": {
                        "version": "2",
                        "tools": [{"type": "web_search"}],
                    }
                }
            },
            {"version": "3"},
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
            client,
            project_endpoint="https://proj",
            agent_id=agent_id,
            enable_port_mcp=True,
            port_access_token="tok",
            existing_tools=[
                {
                    "type": "mcp",
                    "server_url": f"https://proj/toolboxes/{tb}/mcp",
                }
            ],
            agent_kind="prompt",
            use_existing_toolbox=True,
        ) == (tb, "3")
    posted = client.send_api_request.await_args_list[1].kwargs["json_body"]["tools"]
    assert any(t.get("type") == "web_search" for t in posted)
    assert any(
        t.get("server_label") == PORT_MCP_SERVER_LABEL
        and t.get("project_connection_id") == port_conn
        for t in posted
    )
    assert client.send_api_request.await_count == 2
