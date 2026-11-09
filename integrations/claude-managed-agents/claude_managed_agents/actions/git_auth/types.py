from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedGitAccess:
    mount_token: str
