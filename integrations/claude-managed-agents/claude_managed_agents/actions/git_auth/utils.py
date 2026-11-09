from __future__ import annotations

from claude_managed_agents.actions.git_auth.types import (
    AgentMcpEnsureSpec,
    GITHUB_MCP_SERVER_NAME,
    GitAuthRequest,
    McpCredentialSpec,
    ResolvedGitAccess,
    github_mcp_url,
)


def resolve_git_auth(request: GitAuthRequest) -> ResolvedGitAccess:
    mcp: McpCredentialSpec | None = None
    agent_mcp: AgentMcpEnsureSpec | None = None
    if request.enable_git_mcp:
        mcp_url = github_mcp_url(request.git_mcp_server_url)
        mcp = McpCredentialSpec(mcp_server_url=mcp_url, token=request.access_token)
        agent_mcp = AgentMcpEnsureSpec(name=GITHUB_MCP_SERVER_NAME, url=mcp_url)

    return ResolvedGitAccess(
        mount_token=request.access_token,
        mcp=mcp,
        agent_mcp=agent_mcp,
    )
