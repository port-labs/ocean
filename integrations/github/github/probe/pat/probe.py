import re

from github.clients.constants import SKIP_RETRY_CONFIG
from github.probe.pat.permissions import PatKindPermissionVerdict
from httpx import Response
from port_ocean.context.ocean import ocean
from port_ocean.core.probe import KindPermissionVerdict

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.helpers.api_error_messages import format_github_request_error
from github.probe.base_probe_flow import GitHubPermissionProbeFlow, org_scopes

_FETCH_USER_UNAUTHORIZED_HINT = (
    "Please verify the personal access token is valid and not expired."
)

_FINE_GRAINED_PAT_PREFIX = "github_pat_"
# github_pat_ + 22 alnum + _ + 59 alnum (93 chars total)
_FINE_GRAINED_PAT_RE = re.compile(
    rf"^{_FINE_GRAINED_PAT_PREFIX}[A-Za-z0-9]{{22}}_[A-Za-z0-9]{{59}}$"
)

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
    "fine-grained personal access tokens because GitHub does not expose granted scopes. "
    "You may still be able to ingest data."
)

MALFORMED_FINE_GRAINED_PAT_MESSAGE = (
    "The token starts with 'github_pat_' but does not match the expected "
    "fine-grained personal access token format. Please ensure your token is valid."
)


def is_fine_grained_pat(token: str) -> bool:
    return bool(_FINE_GRAINED_PAT_RE.fullmatch(token))


class GitHubPatPermissionProbe(GitHubPermissionProbeFlow):
    @property
    def _permission_verdict_class(self) -> type[KindPermissionVerdict]:
        return PatKindPermissionVerdict

    async def run(self) -> None:
        authenticator = self.authenticators[0]
        token = (await authenticator.get_token()).token
        if token.startswith(_FINE_GRAINED_PAT_PREFIX):
            if not is_fine_grained_pat(token):
                await self.context.fail(MALFORMED_FINE_GRAINED_PAT_MESSAGE)
                return
            self.context.message = FINE_GRAINED_PAT_MESSAGE
            return

        user_response = await self._fetch_user(authenticator)
        if user_response is None:
            return

        granted_scopes = expand_pat_scopes(self._parse_scopes(user_response))
        organizations = await self._get_organizations(
            authenticator, user_response, granted_scopes
        )
        if organizations is None:
            return

        checks = await self.context.add_scopes(*org_scopes(organizations))  # type: ignore[arg-type]
        permissions = {scope: "granted" for scope in granted_scopes}
        await self._resolve_checks(checks, permissions)

    async def _fetch_user(
        self,
        authenticator: AbstractGitHubAuthenticator,
    ) -> Response | None:
        response = await authenticator.client.get(
            f"{ocean.integration_config['github_host'].rstrip('/')}/user",
            headers=(await authenticator.get_headers()).as_dict(),
            extensions=SKIP_RETRY_CONFIG,
        )
        if not response.is_success:
            await self.context.fail(format_authenticated_user_error(response))
            return None
        return response

    def _parse_scopes(self, user_response: Response) -> set[str]:
        return {
            scope.strip()
            for scope in user_response.headers.get("x-oauth-scopes", "").split(",")
            if scope.strip()
        }

    async def _get_organizations(
        self,
        authenticator: AbstractGitHubAuthenticator,
        user_response: Response,
        granted_scopes: set[str],
    ) -> list[str] | None:
        if authenticator.organization:
            return await self._validate_configured_organization(
                authenticator, user_response, authenticator.organization, granted_scopes
            )

        if "read:org" not in granted_scopes:
            await self.context.fail(
                "Token does not have the 'read:org' scope, unable to fetch accessible organizations"
            )
            return None
        headers = (await authenticator.get_headers()).as_dict()
        github_host = ocean.integration_config["github_host"].rstrip("/")
        organizations: list[str] = []

        user = user_response.json()
        if isinstance(user, dict) and isinstance(login := user.get("login"), str):
            organizations.append(login)

        url: str | None = f"{github_host}/user/orgs"
        params: dict[str, int] | None = {"per_page": 100}
        while url:
            response = await authenticator.client.get(
                url,
                headers=headers,
                params=params,
                extensions=SKIP_RETRY_CONFIG,
            )
            if not response.is_success:
                await self.context.fail(
                    f"Failed to fetch organizations: GitHub API returned {response.status_code}"
                )
                return None
            for organization in response.json():
                if not isinstance(organization, dict):
                    continue
                login = organization.get("login")
                if isinstance(login, str) and login not in organizations:
                    organizations.append(login)
            next_link = response.links.get("next")
            url = next_link.get("url") if next_link else None
            params = None
        return organizations

    async def _validate_configured_organization(
        self,
        authenticator: AbstractGitHubAuthenticator,
        user_response: Response,
        organization: str,
        granted_scopes: set[str],
    ) -> list[str] | None:
        user = user_response.json()
        if (
            isinstance(user, dict)
            and isinstance(login := user.get("login"), str)
            and login.casefold() == organization.casefold()
        ):
            return [login]

        if "read:org" not in granted_scopes:
            await self.context.fail(
                f"Token does not have the 'read:org' scope, unable to validate access to org {authenticator.organization}"
            )
            return None

        github_host = ocean.integration_config["github_host"].rstrip("/")
        response = await authenticator.client.get(
            f"{github_host}/user/memberships/orgs/{organization}",
            headers=(await authenticator.get_headers()).as_dict(),
            extensions=SKIP_RETRY_CONFIG,
        )
        if response.status_code == 200:
            membership = response.json()
            if isinstance(membership, dict) and membership.get("state") == "active":
                return [organization]
            await self.context.fail(
                f"Configured organization '{organization}' has a pending membership "
                "that has not been accepted yet"
            )
            return None

        if response.status_code in (403, 404):
            await self.context.fail(
                f"Configured organization '{organization}' was not found "
                "or the token does not have access to it"
            )
            return None

        await self.context.fail(
            f"Failed to verify organization '{organization}': "
            f"GitHub API returned {response.status_code}"
        )
        return None


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


def format_authenticated_user_error(response: Response) -> str:
    """Build a user-facing failure message for a failed GET /user probe request."""
    return format_github_request_error(
        response,
        action="Failed to fetch authenticated user",
        unauthorized_hint=_FETCH_USER_UNAUTHORIZED_HINT,
    )
