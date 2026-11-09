from __future__ import annotations

from claude_managed_agents.actions.git_auth.types import ResolvedGitAccess


def resolve_git_auth(access_token: str) -> ResolvedGitAccess:
    return ResolvedGitAccess(mount_token=access_token)
