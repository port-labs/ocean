from typing import TYPE_CHECKING, Any, cast

from loguru import logger
from port_ocean.context.event import event

from github.clients.auth.abstract_authenticator import AuthScope
from github.clients.auth.github_app.authenticator import GitHubAppAuthenticator
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from github.helpers.exceptions import AuthenticationException

if TYPE_CHECKING:
    from integration import GithubPortAppConfig

_scopes_by_org: dict[str, AuthScope] | None = None


def reset_installation_index() -> None:
    global _scopes_by_org
    _scopes_by_org = None


class GitHubAppInstallationRegistry:
    @classmethod
    def _allowed_organizations(cls) -> list[str]:
        try:
            port_app_config = cast("GithubPortAppConfig", event.port_app_config)
            return port_app_config.organizations or []
        except Exception:
            return []

    @classmethod
    def _is_allowed_org(
        cls, config: dict[str, Any], login: str, allowed: list[str]
    ) -> bool:
        if config.get("github_organization") and login != config["github_organization"]:
            return False
        if allowed and login not in allowed:
            return False
        return True

    @classmethod
    def _authenticator(
        cls,
        config: dict[str, Any],
        *,
        installation_id: str,
        organization: str | None = None,
    ) -> GitHubAppInstallationAuthenticator:
        return GitHubAppInstallationAuthenticator(
            app_id=config["github_app_id"],
            private_key=config["github_app_private_key"],
            installation_id=installation_id,
            github_host=config["github_host"],
            organization=organization,
        )

    @classmethod
    def _scope_from_installation(
        cls, config: dict[str, Any], installation: dict[str, Any]
    ) -> AuthScope:
        account = installation["account"]
        login = account["login"]
        installation_id = str(installation["id"])
        return AuthScope(
            organization=login,
            account_type=account.get("type"),
            installation_id=installation_id,
            authenticator=cls._authenticator(
                config, installation_id=installation_id, organization=login
            ),
        )

    @classmethod
    async def _ensure_index(cls, config: dict[str, Any]) -> dict[str, AuthScope]:
        global _scopes_by_org
        if _scopes_by_org is not None:
            return _scopes_by_org

        app_auth = GitHubAppAuthenticator.from_config(config)
        installation_id = config.get("github_app_installation_id")

        if installation_id:
            organization = config.get("github_organization")
            account_type = None
            if not organization:
                installation = await app_auth.fetch_installation(str(installation_id))
                account = installation.get("account") or {}
                organization = account.get("login")
                account_type = account.get("type")
                if not organization:
                    raise AuthenticationException(
                        "GitHub App installation has no account login"
                    )
            scope = AuthScope(
                organization=organization,
                account_type=account_type,
                installation_id=str(installation_id),
                authenticator=cls._authenticator(
                    config,
                    installation_id=str(installation_id),
                    organization=organization,
                ),
            )
            _scopes_by_org = {organization: scope}
            return _scopes_by_org

        allowed_orgs = cls._allowed_organizations()
        index: dict[str, AuthScope] = {}

        async for page in app_auth.iter_app_installations():
            for installation in page:
                account = installation.get("account") or {}
                login = account.get("login")
                if not login or not cls._is_allowed_org(config, login, allowed_orgs):
                    continue
                index[login] = cls._scope_from_installation(config, installation)

        _scopes_by_org = index
        return _scopes_by_org

    @classmethod
    async def list_scopes(cls, config: dict[str, Any]) -> list[AuthScope]:
        scopes = list((await cls._ensure_index(config)).values())
        if not scopes:
            raise AuthenticationException("No GitHub App installations found")
        logger.info(f"Discovered {len(scopes)} GitHub App installation(s)")
        return scopes

    @classmethod
    def for_org(
        cls, config: dict[str, Any], organization: str
    ) -> GitHubAppInstallationAuthenticator:
        if _scopes_by_org and organization in _scopes_by_org:
            return cast(
                GitHubAppInstallationAuthenticator,
                _scopes_by_org[organization].authenticator,
            )

        installation_id = config.get("github_app_installation_id")
        if installation_id and (
            not config.get("github_organization")
            or config["github_organization"] == organization
        ):
            return cls._authenticator(
                config,
                installation_id=str(installation_id),
                organization=organization,
            )

        raise AuthenticationException(
            f"No GitHub App installation found for organization '{organization}'. "
            "Run a full resync or configure github_app_installation_id."
        )
