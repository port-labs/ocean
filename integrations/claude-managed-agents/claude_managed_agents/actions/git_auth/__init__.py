from claude_managed_agents.actions.git_auth.mcp import (
    attach_git_mcp_settings_to_agent_config,
    ensure_git_mcp_credential,
    is_agent_configured_with_git_mcp,
)
from claude_managed_agents.actions.git_auth.types import (
    AgentMcpEnsureSpec,
    GitAuthRequest,
    ResolvedGitAccess,
)
from claude_managed_agents.actions.git_auth.utils import resolve_git_auth

__all__ = [
    "AgentMcpEnsureSpec",
    "GitAuthRequest",
    "ResolvedGitAccess",
    "attach_git_mcp_settings_to_agent_config",
    "ensure_git_mcp_credential",
    "is_agent_configured_with_git_mcp",
    "resolve_git_auth",
]
