import asyncio

from loguru import logger
from port_ocean.context.ocean import ocean

from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from github.helpers.exceptions import AuthenticationException

_authenticators_by_org: dict[str, GitHubAppInstallationAuthenticator] | None = None
_ensure_lock = asyncio.Lock()


def reset_authenticators_by_org() -> None:
    global _authenticators_by_org
    _authenticators_by_org = None


def _authenticator(installation_id: str) -> GitHubAppInstallationAuthenticator:
    return GitHubAppInstallationAuthenticator(
        app_id=ocean.integration_config["github_app_id"],
        private_key=ocean.integration_config["github_app_private_key"],
        installation_id=installation_id,
        github_host=ocean.integration_config["github_host"],
    )


async def _discover_authenticators() -> dict[str, GitHubAppInstallationAuthenticator]:
    global _authenticators_by_org
    if _authenticators_by_org is not None:
        return _authenticators_by_org

    async with _ensure_lock:
        if _authenticators_by_org is None:
            app_auth = GitHubAppAuthenticator.from_config(ocean.integration_config)
            index: dict[str, GitHubAppInstallationAuthenticator] = {}
            async for page in app_auth.iter_app_installations():
                for installation in page:
                    login = (installation.get("account") or {}).get("login")
                    if not login:
                        raise AuthenticationException(
                            f"No login found for installation {installation}"
                        )
                    index[login] = _authenticator(
                        installation_id=str(installation["id"])
                    )
            _authenticators_by_org = index
    return _authenticators_by_org


async def list_installations_authenticators() -> list[GitHubAppInstallationAuthenticator]:
    by_org = await _discover_authenticators()
    authenticators = list(by_org.values())
    if not authenticators:
        raise AuthenticationException("No GitHub App installations found")

    logger.info(f"Discovered {len(authenticators)} GitHub App installation(s)")
    return authenticators


async def get_installation_authenticator_for_organization(
    organization: str,
) -> GitHubAppInstallationAuthenticator:
    by_org = await _discover_authenticators()
    if organization not in by_org:
        raise AuthenticationException(
            f"No GitHub App installation found for organization '{organization}'"
        )

    return by_org[organization]
