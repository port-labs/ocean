from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from port_ocean.context.ocean import ocean
from port_ocean.core.probe import ProbeCheck, ProbeContext, ProbeStatus

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


@dataclass(frozen=True)
class PermissionSnapshot:
    permissions: dict[str, str] | None
    organization: str | None = None
    scopes: dict[str, str] = field(default_factory=dict)


class GitHubPermissionProbe:
    def __init__(self, context: ProbeContext) -> None:
        self.context = context

    async def run(self) -> None:
        kinds = tuple(self.context.available_kinds)
        provider = get_auth_provider()
        authenticators = await provider.list_authenticators()
        self.context.update_progress()

        if provider.is_app_auth():
            await self._probe_app(kinds, authenticators)
            return

        await self._probe_pat(kinds, authenticators[0])

    async def _probe_app(
        self,
        kinds: tuple[str, ...],
        authenticators: Sequence[AbstractGitHubAuthenticator],
    ) -> None:
        snapshots: list[PermissionSnapshot] = []
        for authenticator in authenticators:
            snapshots.append(
                PermissionSnapshot(
                    organization=authenticator.organization,
                    permissions=(await authenticator.get_token()).permissions,
                )
            )
            self.context.update_progress()
        for snapshot in _with_org_scopes(snapshots):
            self._record_snapshot(kinds, snapshot, _app_check)

    async def _probe_pat(
        self,
        kinds: tuple[str, ...],
        authenticator: AbstractGitHubAuthenticator,
    ) -> None:
        granted_scopes = await self._get_pat_scopes(authenticator)
        self.context.update_progress()
        organizations = await self._get_pat_organizations(authenticator)
        snapshots = _with_org_scopes(
            [
                PermissionSnapshot(
                    organization=organization,
                    permissions=(
                        {
                            scope: "granted"
                            for scope in _expand_pat_scopes(granted_scopes)
                        }
                        if granted_scopes is not None
                        else None
                    ),
                )
                for organization in organizations
            ]
        )
        for snapshot in snapshots:
            self._record_snapshot(kinds, snapshot, _pat_check)

    def _record_snapshot(
        self,
        kinds: tuple[str, ...],
        snapshot: PermissionSnapshot,
        check: Callable[[str, PermissionSnapshot], ProbeCheck],
    ) -> None:
        for kind in kinds:
            self.context.result.results.append(check(kind, snapshot))
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
            self.context.update_progress()
            next_link = response.links.get("next")
            url = next_link.get("url") if next_link else None
            params = None
        if organizations:
            return organizations
        return [None]


def _with_org_scopes(
    snapshots: list[PermissionSnapshot],
) -> list[PermissionSnapshot]:
    is_multi_org = len(snapshots) > 1
    return [
        PermissionSnapshot(
            permissions=snapshot.permissions,
            organization=snapshot.organization,
            scopes=(
                {"org": snapshot.organization}
                if is_multi_org and snapshot.organization
                else {}
            ),
        )
        for snapshot in snapshots
    ]


def _app_check(kind: str, snapshot: PermissionSnapshot) -> ProbeCheck:
    required_permissions = APP_KIND_PERMISSIONS.get(kind)
    if required_permissions is None:
        return ProbeCheck(
            status=ProbeStatus.UNKNOWN,
            message=f"No GitHub App permission mapping is defined for {kind}",
            kind=kind,
            scopes=snapshot.scopes,
        )
    if snapshot.permissions is None:
        return ProbeCheck(
            status=ProbeStatus.UNKNOWN,
            message="GitHub did not return permissions for the installation token",
            kind=kind,
            scopes=snapshot.scopes,
        )

    granted: tuple[str, str] | None = None
    for permission in required_permissions:
        actual = snapshot.permissions.get(permission, "")
        if _PERMISSION_LEVELS.get(actual, 0) >= _PERMISSION_LEVELS["read"]:
            granted = (permission, actual)
            break
    return ProbeCheck(
        status=ProbeStatus.SUCCESS if granted else ProbeStatus.FAILURE,
        message=(
            f"GitHub App has {granted[1]} access for {granted[0]}"
            if granted
            else "GitHub App requires read access for "
            + " or ".join(required_permissions)
        ),
        kind=kind,
        scopes=snapshot.scopes,
    )


def _pat_check(kind: str, snapshot: PermissionSnapshot) -> ProbeCheck:
    required = PAT_KIND_SCOPES.get(kind)
    if snapshot.permissions is None:
        return ProbeCheck(
            status=ProbeStatus.UNKNOWN,
            message=(
                "GitHub does not expose granted scopes for this token; "
                "this is expected for fine-grained personal access tokens"
            ),
            kind=kind,
            scopes=snapshot.scopes,
        )
    if required is None:
        return ProbeCheck(
            status=ProbeStatus.UNKNOWN,
            message=f"No personal access token scope mapping is defined for {kind}",
            kind=kind,
            scopes=snapshot.scopes,
        )

    has_scope = required in snapshot.permissions
    return ProbeCheck(
        status=ProbeStatus.SUCCESS if has_scope else ProbeStatus.FAILURE,
        message=(
            f"Personal access token grants {required}"
            if has_scope
            else f"Personal access token requires {required} for private resources"
        ),
        kind=kind,
        scopes=snapshot.scopes,
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
