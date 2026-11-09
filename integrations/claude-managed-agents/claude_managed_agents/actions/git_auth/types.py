from __future__ import annotations

from dataclasses import dataclass

from claude_managed_agents.actions.mcp_vault_utils import normalize_mcp_server_url

DEFAULT_GITHUB_MCP_SERVER_URL = "https://api.githubcopilot.com/mcp/"
GITHUB_MCP_SERVER_NAME = "github"
GITHUB_MCP_CREDENTIAL_NAME = "github-mcp"


@dataclass(frozen=True)
class McpCredentialSpec:
    mcp_server_url: str
    token: str
    display_name: str = GITHUB_MCP_CREDENTIAL_NAME


@dataclass(frozen=True)
class AgentMcpEnsureSpec:
    name: str
    url: str


@dataclass(frozen=True)
class ResolvedGitAccess:
    mount_token: str
    mcp: McpCredentialSpec | None
    agent_mcp: AgentMcpEnsureSpec | None


def github_mcp_url(override: str | None) -> str:
    return normalize_mcp_server_url(override or DEFAULT_GITHUB_MCP_SERVER_URL)
