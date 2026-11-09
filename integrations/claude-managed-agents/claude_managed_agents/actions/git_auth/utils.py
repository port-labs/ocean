from __future__ import annotations

from claude_managed_agents.actions.git_auth.types import (
    AgentMcpEnsureSpec,
    GITHUB_MCP_SERVER_NAME,
    McpCredentialSpec,
    ResolvedGitAccess,
    github_mcp_url,
)


def resolve_git_auth(
    access_token: str,
    *,
    enable_git_mcp: bool = True,
    git_mcp_server_url: str | None = None,
) -> ResolvedGitAccess:
    mcp: McpCredentialSpec | None = None
    agent_mcp: AgentMcpEnsureSpec | None = None
    if enable_git_mcp:
        mcp_url = github_mcp_url(git_mcp_server_url)
        mcp = McpCredentialSpec(mcp_server_url=mcp_url, token=access_token)
        agent_mcp = AgentMcpEnsureSpec(name=GITHUB_MCP_SERVER_NAME, url=mcp_url)

    return ResolvedGitAccess(
        mount_token=access_token,
        mcp=mcp,
        agent_mcp=agent_mcp,
    )
