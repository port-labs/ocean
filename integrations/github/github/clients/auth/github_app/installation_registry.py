from typing import Any

from loguru import logger

from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from github.helpers.exceptions import AuthenticationException

_authenticators_by_org: dict[str, GitHubAppInstallationAuthenticator] | None = None


def reset_authenticators_by_org() -> None:
    global _authenticators_by_org
    _authenticators_by_org = None


class GitHubAppInstallationRegistry:
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
    async def _get_authenticators_by_org(
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

        index: dict[str, GitHubAppInstallationAuthenticator] = {}

        async for page in app_auth.iter_app_installations():
            for installation in page:
                account = installation.get("account") or {}
                login = account.get("login")
                if not login:
                    continue
                index[login] = cls._authenticator(
                    config, installation_id=str(installation["id"])
                )

        _authenticators_by_org = index
        return _authenticators_by_org

    @classmethod
    async def list_authenticators(
        cls, config: dict[str, Any]
    ) -> list[GitHubAppInstallationAuthenticator]:
        authenticators = list((await cls._get_authenticators_by_org(config)).values())
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
