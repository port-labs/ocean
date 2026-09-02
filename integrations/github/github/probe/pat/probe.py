from github.probe.pat.permissions import PatKindPermissionVerdict
from port_ocean.context.ocean import ocean
from port_ocean.core.probe import KindPermissionVerdict
from port_ocean.helpers.retry import SKIP_RETRY_EXTENSION_KEY

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.probe.base_probe_flow import GitHubPermissionProbeFlow, org_scopes


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
        organizations = await self._get_organizations(authenticator)
        granted_scopes = await self._get_scopes(authenticator)
        if granted_scopes is None:
            await self.context.fail(FINE_GRAINED_PAT_MESSAGE)
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
