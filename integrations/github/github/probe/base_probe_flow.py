from abc import ABC, abstractmethod
from typing import Sequence

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from port_ocean.core.probe import ProbeContext, ProbeCheck, KindPermissionVerdict


class GitHubPermissionProbeFlow(ABC):
    def __init__(
        self,
        context: ProbeContext,
        authenticators: Sequence[AbstractGitHubAuthenticator],
    ) -> None:
        self.context = context
        self.authenticators = authenticators
        self.permission_verdict = self._permission_verdict_class()

    @abstractmethod
    async def run(self) -> None:
        """Probe permissions for one GitHub authentication flow."""

    @property
    @abstractmethod
    def _permission_verdict_class(self) -> type[KindPermissionVerdict]:
        pass

    async def _resolve_checks(
        self,
        checks: Sequence[ProbeCheck],
        permissions: dict[str, str],
    ) -> None:
        for check in checks:
            check.status, check.message = self.permission_verdict.verdict(check.kind, permissions)
        await self.context.update_progress()


def org_scopes(organizations: Sequence[str | None]) -> list[dict[str, str]]:
    is_multi_org = len(organizations) > 1
    return [
        {"org": organization} if is_multi_org and organization else {}
        for organization in organizations
    ]
