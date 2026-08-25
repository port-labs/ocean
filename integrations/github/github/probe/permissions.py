from collections.abc import Iterable
from dataclasses import dataclass

from port_ocean.context.ocean import ocean
from port_ocean.core.probe import ProbeCheck, ProbeStatus

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
    authentication: str
    permissions: dict[str, str] | None
    organization: str | None = None


async def probe_github_permissions(kinds: Iterable[str]) -> list[ProbeCheck]:
    """Resolve effective GitHub permissions and evaluate every declared kind."""
    kinds = tuple(kinds)
    provider = get_auth_provider()
    authenticators = await provider.list_authenticators()
    is_multi_org = len(authenticators) > 1

    if provider.is_app_auth():
        snapshots = [
            PermissionSnapshot(
                authentication="github-app",
                organization=authenticator.organization,
                permissions=(await authenticator.get_token()).permissions,
            )
            for authenticator in authenticators
        ]
        return [
            _app_check(kind, snapshot, is_multi_org)
            for snapshot in snapshots
            for kind in kinds
        ]

    authenticator = authenticators[0]
    scopes = await _get_pat_scopes(authenticator)
    snapshot = PermissionSnapshot(
        authentication="personal-access-token",
        organization=authenticator.organization,
        permissions=(
            {scope: "granted" for scope in _expand_pat_scopes(scopes)}
            if scopes is not None
            else None
        ),
    )
    return [_pat_check(kind, snapshot, is_multi_org) for kind in kinds]


async def _get_pat_scopes(
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


def _app_check(
    kind: str, snapshot: PermissionSnapshot, is_multi_org: bool
) -> ProbeCheck:
    required_permissions = APP_KIND_PERMISSIONS.get(kind)
    scopes = _org_scopes(snapshot, is_multi_org)
    if required_permissions is None:
        return ProbeCheck(
            status=ProbeStatus.UNKNOWN,
            message=f"No GitHub App permission mapping is defined for {kind}",
            kind=kind,
            scopes=scopes,
        )
    if snapshot.permissions is None:
        return ProbeCheck(
            status=ProbeStatus.UNKNOWN,
            message="GitHub did not return permissions for the installation token",
            kind=kind,
            scopes=scopes,
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
        scopes=scopes,
    )


def _pat_check(
    kind: str, snapshot: PermissionSnapshot, is_multi_org: bool
) -> ProbeCheck:
    required = PAT_KIND_SCOPES.get(kind)
    scopes = _org_scopes(snapshot, is_multi_org)
    if snapshot.permissions is None:
        return ProbeCheck(
            status=ProbeStatus.UNKNOWN,
            message=(
                "GitHub does not expose granted scopes for this token; "
                "this is expected for fine-grained personal access tokens"
            ),
            kind=kind,
            scopes=scopes,
        )
    if required is None:
        return ProbeCheck(
            status=ProbeStatus.UNKNOWN,
            message=f"No personal access token scope mapping is defined for {kind}",
            kind=kind,
            scopes=scopes,
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
        scopes=scopes,
    )


def _org_scopes(snapshot: PermissionSnapshot, is_multi_org: bool) -> dict[str, str]:
    if is_multi_org and snapshot.organization:
        return {"org": snapshot.organization}
    return {}


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
