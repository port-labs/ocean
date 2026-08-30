from port_ocean.core.probe import ProbeCheckStatus

from github.probe.permissions.base import GitHubPermissionProbeFlow, org_scopes

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

_PERMISSION_LEVELS = {"read": 1, "write": 2, "admin": 3}


class GitHubAppPermissionProbe(GitHubPermissionProbeFlow):
    async def run(self) -> None:
        tokens = [
            await authenticator.get_token() for authenticator in self.authenticators
        ]
        pending = self.context.add_scopes(
            *org_scopes(
                [authenticator.organization for authenticator in self.authenticators]
            )
        )
        kind_count = len(self.context.available_kinds)
        for index, token in enumerate(tokens):
            checks = pending[index * kind_count : (index + 1) * kind_count]
            self._resolve_checks(checks, token.permissions, app_permission_verdict)


def app_permission_verdict(
    kind: str,
    permissions: dict[str, str] | None,
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
