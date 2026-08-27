from collections.abc import Callable, Sequence

from port_ocean.context.ocean import ocean
from port_ocean.core.probe import ProbeCheck, ProbeContext, ProbeCheckStatus

from github.clients.auth import get_auth_provider
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator

APP_KIND_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "organization": ("metadata",),
    "repository": ("metadata",),
    "folder": ("contents",),
    "file": ("contents",),
    "skill": ("contents",),
    "plugin": ("contents",),
    "user": ("members",),
    "team": ("members",),
    "workflow": ("actions",),
    "workflow-run": ("actions",),
    "pull-request": ("pull_requests",),
    "issue": ("issues",),
    "release": ("contents",),
    "tag": ("contents",),
    "branch": ("contents",),
    "environment": ("environments",),
    "deployment": ("deployments",),
    "deployment-status": ("deployments",),
    "dependabot-alert": ("vulnerability_alerts",),
    "code-scanning-alerts": ("security_events",),
    "secret-scanning-alerts": ("secret_scanning_alerts",),
    "collaborator": ("metadata",),
    "package": ("organization_packages", "packages"),
}

PAT_KIND_SCOPES: dict[str, str] = {
    "organization": "read:org",
    "repository": "repo",
    "folder": "repo",
    "file": "repo",
    "skill": "repo",
    "plugin": "repo",
    "user": "read:org",
    "team": "read:org",
    "workflow": "repo",
    "workflow-run": "repo",
    "pull-request": "repo",
    "issue": "repo",
    "release": "repo",
    "tag": "repo",
    "branch": "repo",
    "environment": "repo",
    "deployment": "repo",
    "deployment-status": "repo",
    "dependabot-alert": "security_events",
    "code-scanning-alerts": "security_events",
    "secret-scanning-alerts": "security_events",
    "collaborator": "repo",
    "package": "read:packages",
}

_PERMISSION_LEVELS = {"read": 1, "write": 2, "admin": 3}
# Nested classic OAuth scopes from GitHub's scopes-for-oauth-apps docs.
_IMPLIED_PAT_SCOPES: dict[str, set[str]] = {
    "repo": {
        "repo:status",
        "repo_deployment",
        "public_repo",
        "repo:invite",
        "security_events",
    },
    "admin:repo_hook": {"write:repo_hook", "read:repo_hook"},
    "write:repo_hook": {"read:repo_hook"},
    "admin:org": {"write:org", "read:org"},
    "write:org": {"read:org"},
    "admin:public_key": {"write:public_key", "read:public_key"},
    "write:public_key": {"read:public_key"},
    "user": {"read:user", "user:email", "user:follow"},
    "project": {"read:project"},
    "delete:packages": {"write:packages", "read:packages"},
    "write:packages": {"read:packages"},
    "admin:gpg_key": {"write:gpg_key", "read:gpg_key"},
    "write:gpg_key": {"read:gpg_key"},
}


class GitHubPermissionProbe:
    def __init__(self, context: ProbeContext) -> None:
        self.context = context

    async def run(self) -> None:
        provider = get_auth_provider()
        authenticators = await provider.list_authenticators()

        if provider.is_app_auth():
            await self._probe_app(authenticators)
            return

        await self._probe_pat(authenticators[0])

    async def _probe_app(
        self,
        authenticators: Sequence[AbstractGitHubAuthenticator],
    ) -> None:
        pending = self.context.add_scopes(
            *_org_scopes(
                [authenticator.organization for authenticator in authenticators]
            )
        )
        for authenticator, checks in zip(authenticators, pending):
            token = await authenticator.get_token()
            self._resolve_checks(checks, token.permissions, _app_verdict)

    async def _probe_pat(
        self,
        authenticator: AbstractGitHubAuthenticator,
    ) -> None:
        organizations = await self._get_pat_organizations(authenticator)
        checks = self.context.add_scopes(*_org_scopes(organizations))

        granted_scopes = await self._get_pat_scopes(authenticator)
        permissions = (
            {scope: "granted" for scope in _expand_pat_scopes(granted_scopes)}
            if granted_scopes is not None
            else None
        )

        self._resolve_checks(checks, permissions, _pat_verdict)

    def _resolve_checks(
        self,
        checks: list[ProbeCheck],
        permissions: dict[str, str] | None,
        verdict: Callable[[str, dict[str, str] | None], tuple[ProbeCheckStatus, str]],
    ) -> None:
        for check in checks:
            if check.kind is None:
                continue
            check.status, check.message = verdict(check.kind, permissions)
        self.context.update_progress()

    async def _get_pat_scopes(
        self,
        authenticator: AbstractGitHubAuthenticator,
    ) -> set[str] | None:
        response = await authenticator.client.get(
            f"{ocean.integration_config['github_host'].rstrip('/')}/user",
            headers=(await authenticator.get_headers()).as_dict(),
        )
        response.raise_for_status()
        if "x-oauth-scopes" not in response.headers:
            return None
        return {
            scope.strip()
            for scope in response.headers["x-oauth-scopes"].split(",")
            if scope.strip()
        }

    async def _get_pat_organizations(
        self,
        authenticator: AbstractGitHubAuthenticator,
    ) -> list[str | None]:
        if authenticator.organization:
            return [authenticator.organization]

        headers = (await authenticator.get_headers()).as_dict()
        url: str | None = (
            f"{ocean.integration_config['github_host'].rstrip('/')}/user/orgs"
        )
        organizations: list[str | None] = []
        params: dict[str, int] | None = {"per_page": 100}
        while url:
            response = await authenticator.client.get(
                url,
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            organizations.extend(
                login
                for organization in response.json()
                if isinstance(organization, dict)
                and isinstance(login := organization.get("login"), str)
                and login not in organizations
            )
            next_link = response.links.get("next")
            url = next_link.get("url") if next_link else None
            params = None
        if organizations:
            return organizations
        return [None]


def _org_scopes(organizations: Sequence[str | None]) -> list[dict[str, str]]:
    is_multi_org = len(organizations) > 1
    return [
        {"org": organization} if is_multi_org and organization else {}
        for organization in organizations
    ]


def _app_verdict(
    kind: str, permissions: dict[str, str] | None
) -> tuple[ProbeCheckStatus, str]:
    required_permissions = APP_KIND_PERMISSIONS.get(kind)
    if required_permissions is None:
        return (
            ProbeCheckStatus.UNKNOWN,
            f"No GitHub App permission mapping is defined for {kind}",
        )
    if permissions is None:
        return (
            ProbeCheckStatus.UNKNOWN,
            "GitHub did not return permissions for the installation token",
        )

    for permission in required_permissions:
        actual = permissions.get(permission, "")
        if _PERMISSION_LEVELS.get(actual, 0) >= _PERMISSION_LEVELS["read"]:
            return (
                ProbeCheckStatus.SUCCESS,
                f"GitHub App has {actual} access for {permission}",
            )
    return (
        ProbeCheckStatus.FAILURE,
        "GitHub App requires read access for " + " or ".join(required_permissions),
    )


def _pat_verdict(
    kind: str, permissions: dict[str, str] | None
) -> tuple[ProbeCheckStatus, str]:
    required = PAT_KIND_SCOPES.get(kind)
    if permissions is None:
        return (
            ProbeCheckStatus.UNKNOWN,
            "GitHub does not expose granted scopes for this token; "
            "this is expected for fine-grained personal access tokens",
        )
    if required is None:
        return (
            ProbeCheckStatus.UNKNOWN,
            f"No personal access token scope mapping is defined for {kind}",
        )
    if required in permissions:
        return (ProbeCheckStatus.SUCCESS, f"Personal access token grants {required}")
    return (
        ProbeCheckStatus.FAILURE,
        f"Personal access token requires {required} for private resources",
    )


def _expand_pat_scopes(scopes: set[str]) -> set[str]:
    expanded = set(scopes)
    pending = list(scopes)
    while pending:
        scope = pending.pop()
        for implied in _IMPLIED_PAT_SCOPES.get(scope, set()):
            if implied not in expanded:
                expanded.add(implied)
                pending.append(implied)
    return expanded
