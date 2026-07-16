import asyncio

from loguru import logger

from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from github.helpers.exceptions import AuthenticationException

_authenticators_by_org: dict[str, GitHubAppInstallationAuthenticator] = {}
_discovery_lock = asyncio.Lock()


def reset_authenticators_by_org() -> None:
    global _authenticators_by_org
    _authenticators_by_org = {}


def _authenticator(
    organization: str, installation_id: str
) -> GitHubAppInstallationAuthenticator:
    return GitHubAppInstallationAuthenticator(
        app_auth=GitHubAppAuthenticator.from_config(),
        organization=organization,
        installation_id=installation_id,
    )


async def _fetch_installations() -> dict[str, GitHubAppInstallationAuthenticator]:
    app_auth = GitHubAppAuthenticator.from_config()
    index: dict[str, GitHubAppInstallationAuthenticator] = {}
    async for page in app_auth.iter_app_installations():
        for installation in page:
            login = (installation.get("account") or {}).get("login")
            if not login:
                raise AuthenticationException(
                    f"No login found for installation {installation}"
                )
            index[login] = _authenticator(
                organization=login, installation_id=str(installation["id"])
            )
    return index


async def _discover_installations() -> None:
    global _authenticators_by_org
    async with _discovery_lock:
        if _authenticators_by_org:
            return

        _authenticators_by_org = await _fetch_installations()


async def list_installations_authenticators() -> (
    list[GitHubAppInstallationAuthenticator]
):
    await _discover_installations()
    if not _authenticators_by_org:
        raise AuthenticationException("No GitHub App installations found")

    authenticators = list(_authenticators_by_org.values())
    logger.info(f"Discovered {len(authenticators)} GitHub App installation(s)")
    return authenticators


async def get_installation_authenticator_for_organization(
    organization: str,
) -> GitHubAppInstallationAuthenticator:
    await _discover_installations()
    if organization not in _authenticators_by_org:
        raise AuthenticationException(
            f"No GitHub App installation found for organization '{organization}'"
        )

    return _authenticators_by_org[organization]
