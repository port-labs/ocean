from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from claude_managed_agents.actions.exceptions import InvalidActionParametersException
from claude_managed_agents.actions.git_auth import resolve_git_auth
from claude_managed_agents.actions.git_auth.mcp import (
    attach_git_mcp_settings_to_agent_config,
    is_agent_configured_with_git_mcp,
)
from claude_managed_agents.actions.git_auth.types import (
    AgentMcpEnsureSpec,
    DEFAULT_GITHUB_MCP_SERVER_URL,
    GITHUB_MCP_SERVER_NAME,
)
from claude_managed_agents.actions.trigger_agent_executor import TriggerAgentInputs


def test_trigger_agent_inputs_resolves_git_access_from_token() -> None:
    inputs = TriggerAgentInputs.model_validate(
        {
            "agentId": "a1",
            "prompt": "go",
            "environmentId": "e1",
            "gitAccessToken": "ghp_x",
        }
    )
    assert inputs.git_access is not None
    assert inputs.git_access.mount_token == "ghp_x"
    assert inputs.git_access.mcp is not None
    assert inputs.git_access.agent_mcp is not None


def test_trigger_agent_inputs_ignores_git_fields_without_token() -> None:
    inputs = TriggerAgentInputs.model_validate(
        {
            "agentId": "a1",
            "prompt": "go",
            "environmentId": "e1",
            "gitProvider": "github",
            "gitAuthMethod": "pat",
            "gitMcpServerUrl": "https://example.com/mcp",
        }
    )
    assert inputs.git_access is None


@pytest.mark.parametrize(
    ("execution_properties", "match"),
    [
        ({"gitProvider": "gitlab"}, "gitProvider"),
        ({"gitAuthMethod": "github_app"}, "gitAuthMethod"),
        ({"gitAccessToken": ""}, "gitAccessToken"),
    ],
)
def test_trigger_agent_inputs_rejects_invalid_git_auth(
    execution_properties: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(InvalidActionParametersException, match=match):
        TriggerAgentInputs.from_execution_properties(
            {
                "agentId": "a1",
                "prompt": "go",
                "environmentId": "e1",
                **execution_properties,
            }
        )


def test_resolve_git_auth_with_mcp() -> None:
    resolved = resolve_git_auth("ghp_test", enable_git_mcp=True)
    assert resolved.mount_token == "ghp_test"
    assert resolved.mcp is not None
    assert resolved.mcp.token == "ghp_test"
    assert resolved.mcp.mcp_server_url == DEFAULT_GITHUB_MCP_SERVER_URL.rstrip("/")
    assert resolved.agent_mcp is not None
    assert resolved.agent_mcp.name == GITHUB_MCP_SERVER_NAME


def test_resolve_git_auth_skips_mcp_when_disabled() -> None:
    resolved = resolve_git_auth("ghp_test", enable_git_mcp=False)
    assert resolved.mount_token == "ghp_test"
    assert resolved.mcp is None
    assert resolved.agent_mcp is None


def test_attach_git_mcp_settings_adds_server_and_toolset() -> None:
    spec = AgentMcpEnsureSpec(
        name=GITHUB_MCP_SERVER_NAME,
        url=DEFAULT_GITHUB_MCP_SERVER_URL.rstrip("/"),
    )
    agent = MagicMock()
    agent.mcp_servers = []
    agent.tools = []
    result = attach_git_mcp_settings_to_agent_config(spec, agent)
    assert any(
        getattr(s, "name", None) == GITHUB_MCP_SERVER_NAME
        for s in result["mcp_servers"]
    )
    assert any(
        (t.get("mcp_server_name") if isinstance(t, dict) else t.mcp_server_name)
        == GITHUB_MCP_SERVER_NAME
        for t in result["tools"]
    )
    assert is_agent_configured_with_git_mcp(result["mcp_servers"], spec)


def test_attach_git_mcp_replaces_stale_server_with_same_name() -> None:
    from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
        BetaManagedAgentsMCPServerURLDefinition,
    )

    spec = AgentMcpEnsureSpec(
        name=GITHUB_MCP_SERVER_NAME,
        url=DEFAULT_GITHUB_MCP_SERVER_URL.rstrip("/"),
    )
    agent = MagicMock()
    agent.mcp_servers = [
        BetaManagedAgentsMCPServerURLDefinition(
            type="url",
            name=GITHUB_MCP_SERVER_NAME,
            url="https://stale.example/mcp",
        )
    ]
    agent.tools = [
        MagicMock(type="mcp_toolset", mcp_server_name=GITHUB_MCP_SERVER_NAME)
    ]
    result = attach_git_mcp_settings_to_agent_config(spec, agent)
    assert is_agent_configured_with_git_mcp(result["mcp_servers"], spec)
    assert len(result["mcp_servers"]) == 1
