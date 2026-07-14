from typing import TYPE_CHECKING, Any, cast

from loguru import logger
from port_ocean.context.event import event

from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from github.helpers.exceptions import AuthenticationException

if TYPE_CHECKING:
    from integration import GithubPortAppConfig

_authenticators_by_org: dict[str, GitHubAppInstallationAuthenticator] | None = None


def reset_installation_index() -> None:
    global _authenticators_by_org
    _authenticators_by_org = None


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
    ) -> GitHubAppInstallationAuthenticator:
        return GitHubAppInstallationAuthenticator(
            app_id=config["github_app_id"],
            private_key=config["github_app_private_key"],
            installation_id=installation_id,
            github_host=config["github_host"],
        )

    @classmethod
    def _authenticator_from_installation(
        cls, config: dict[str, Any], installation: dict[str, Any]
    ) -> GitHubAppInstallationAuthenticator:
        installation_id = str(installation["id"])
        return cls._authenticator(config, installation_id=installation_id)

    @classmethod
    async def _ensure_index(
        cls, config: dict[str, Any]
    ) -> dict[str, GitHubAppInstallationAuthenticator]:
        global _authenticators_by_org
        if _authenticators_by_org is not None:
            return _authenticators_by_org

        app_auth = GitHubAppAuthenticator.from_config(config)
        installation_id = config.get("github_app_installation_id")

        if installation_id:
            organization = config.get("github_organization")
            if not organization:
                installation = await app_auth.fetch_installation(str(installation_id))
                account = installation.get("account") or {}
                organization = account.get("login")
                if not organization:
                    raise AuthenticationException(
                        "GitHub App installation has no account login"
                    )
            authenticator = cls._authenticator(
                config,
                installation_id=str(installation_id),
            )
            _authenticators_by_org = {organization: authenticator}
            return _authenticators_by_org

        allowed_orgs = cls._allowed_organizations()
        index: dict[str, GitHubAppInstallationAuthenticator] = {}

        async for page in app_auth.iter_app_installations():
            for installation in page:
                account = installation.get("account") or {}
                login = account.get("login")
                if not login or not cls._is_allowed_org(config, login, allowed_orgs):
                    continue
                index[login] = cls._authenticator_from_installation(
                    config, installation
                )

        _authenticators_by_org = index
        return _authenticators_by_org

    @classmethod
    async def list_authenticators(
        cls, config: dict[str, Any]
    ) -> list[GitHubAppInstallationAuthenticator]:
        authenticators = list((await cls._ensure_index(config)).values())
        if not authenticators:
            raise AuthenticationException("No GitHub App installations found")
        logger.info(f"Discovered {len(authenticators)} GitHub App installation(s)")
        return authenticators

    @classmethod
    def get_authenticator_for_organization(
        cls, config: dict[str, Any], organization: str
    ) -> GitHubAppInstallationAuthenticator:
        if _authenticators_by_org and organization in _authenticators_by_org:
            return _authenticators_by_org[organization]

        installation_id = config.get("github_app_installation_id")
        if installation_id and (
            not config.get("github_organization")
            or config["github_organization"] == organization
        ):
            return cls._authenticator(
                config,
                installation_id=str(installation_id),
            )

        raise AuthenticationException(
            f"No GitHub App installation found for organization '{organization}'. "
            "Run a full resync or configure github_app_installation_id."
        )
