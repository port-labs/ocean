from abc import ABC, abstractmethod
from collections.abc import Sequence

from port_ocean.core.probe import KindPermissionVerdict, ProbeCheck, ProbeContext

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator


class GitHubPermissionProbeFlow(ABC):
    def __init__(
        self,
        context: ProbeContext,
        authenticators: Sequence[AbstractGitHubAuthenticator],
    ) -> None:
        self.context = context
        self.authenticators = authenticators

    @abstractmethod
    async def run(self) -> None:
        """Probe permissions for one GitHub authentication flow."""

    def _resolve_checks(
        self,
        checks: Sequence[ProbeCheck],
        permissions: dict[str, str],
        verdict: KindPermissionVerdict,
    ) -> None:
        for check in checks:
            check.status, check.message = verdict.verdict(check.kind, permissions)
        self.context.update_progress()


def org_scopes(organizations: Sequence[str | None]) -> list[dict[str, str]]:
    is_multi_org = len(organizations) > 1
    return [
        {"org": organization} if is_multi_org and organization else {}
        for organization in organizations
    ]
