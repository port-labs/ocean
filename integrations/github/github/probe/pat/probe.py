from github.probe.pat.permissions import PatKindPermissionVerdict
from port_ocean.context.ocean import ocean
from port_ocean.core.probe import KindPermissionVerdict
from port_ocean.helpers.retry import SKIP_RETRY_EXTENSION_KEY

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.probe.base_probe_flow import (
    GitHubPermissionProbeFlow,
    discover_organization_logins,
    org_scopes,
)


NO_RETRY = {SKIP_RETRY_EXTENSION_KEY: True}

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


FINE_GRAINED_PAT_MESSAGE = (
    "Your token is valid, but permission verification is not available for "
    "fine-grained personal access tokens because GitHub does not expose granted scopes."
)


def is_fine_grained_pat(token: str) -> bool:
    return token.startswith("github_pat_")


class GitHubPatPermissionProbe(GitHubPermissionProbeFlow):
    def _permission_verdict_class(self) -> type[KindPermissionVerdict]:
        return PatKindPermissionVerdict

    async def run(self) -> None:
        authenticator = self.authenticators[0]
        token = (await authenticator.get_token()).token
        if is_fine_grained_pat(token):
            self.context.message = FINE_GRAINED_PAT_MESSAGE
            return

        organizations = await discover_organization_logins(authenticator)

        granted_scopes = await self._get_scopes(authenticator)
        if granted_scopes is None:
            return

        checks = await self.context.add_scopes(*org_scopes(organizations))
        permissions = {
            scope: "granted" for scope in expand_pat_scopes(granted_scopes)
        }
        await self._resolve_checks(checks, permissions)

    async def _get_scopes(
        self,
        authenticator: AbstractGitHubAuthenticator,
    ) -> set[str] | None:
        response = await authenticator.client.get(
            f"{ocean.integration_config['github_host'].rstrip('/')}/user",
            headers=(await authenticator.get_headers()).as_dict(),
            extensions=NO_RETRY,
        )
        if not response.is_success:
            await self.context.fail(
                f"Failed to fetch PAT scopes: GitHub API returned {response.status_code}"
            )
            return None
        return {
            scope.strip()
            for scope in response.headers.get("x-oauth-scopes", "").split(",")
            if scope.strip()
        }


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
