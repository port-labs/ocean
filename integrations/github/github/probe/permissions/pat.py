from port_ocean.context.ocean import ocean
from port_ocean.core.probe import ProbeCheckStatus
from port_ocean.helpers.retry import SKIP_RETRY_EXTENSION_KEY

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.probe.permissions.base import GitHubPermissionProbeFlow, org_scopes

NO_RETRY = {SKIP_RETRY_EXTENSION_KEY: True}

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


class GitHubPatPermissionProbe(GitHubPermissionProbeFlow):
    async def run(self) -> None:
        authenticator = self.authenticators[0]
        organizations = await self._get_organizations(authenticator)
        granted_scopes = await self._get_scopes(authenticator)
        checks = await self.context.add_scopes(*org_scopes(organizations))

        permissions = (
            {scope: "granted" for scope in expand_pat_scopes(granted_scopes)}
            if granted_scopes is not None
            else None
        )
        await self._resolve_checks(checks, permissions, pat_permission_verdict)

    async def _get_scopes(
        self,
        authenticator: AbstractGitHubAuthenticator,
    ) -> set[str] | None:
        response = await authenticator.client.get(
            f"{ocean.integration_config['github_host'].rstrip('/')}/user",
            headers=(await authenticator.get_headers()).as_dict(),
            extensions=NO_RETRY,
        )
        response.raise_for_status()
        if "x-oauth-scopes" not in response.headers:
            return None
        return {
            scope.strip()
            for scope in response.headers["x-oauth-scopes"].split(",")
            if scope.strip()
        }

    async def _get_organizations(
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
                extensions=NO_RETRY,
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


def pat_permission_verdict(
    kind: str,
    permissions: dict[str, str] | None,
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


def expand_pat_scopes(scopes: set[str]) -> set[str]:
    expanded = set(scopes)
    pending = list(scopes)
    while pending:
        scope = pending.pop()
        for implied in _IMPLIED_PAT_SCOPES.get(scope, set()):
            if implied not in expanded:
                expanded.add(implied)
                pending.append(implied)
    return expanded
