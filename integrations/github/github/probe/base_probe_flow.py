from abc import ABC, abstractmethod
from typing import Sequence

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.client_factory import create_github_client
from github.core.exporters.organization_exporter import RestOrganizationExporter
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


def org_scopes(organizations: Sequence[str]) -> list[dict[str, str]]:
    is_multi_org = len(organizations) > 1
    return [
        {"org": organization} if is_multi_org else {}
        for organization in organizations
    ]


async def discover_organization_logins(
    authenticator: AbstractGitHubAuthenticator,
) -> list[str]:
    if authenticator.organization:
        return [authenticator.organization]

    rest_client = create_github_client(authenticator)
    exporter = RestOrganizationExporter(rest_client)
    organizations: list[str] = []
    async for batch in exporter.get_paginated_resources():
        for organization in batch:
            if (
                isinstance(organization, dict)
                and isinstance(login := organization.get("login"), str)
                and login not in organizations
            ):
                organizations.append(login)
    return organizations
