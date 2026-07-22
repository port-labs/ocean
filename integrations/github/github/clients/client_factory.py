import os
from typing import Dict, Literal, Optional, Type, overload

from loguru import logger
from github.helpers.exceptions import MissingCredentials
from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from port_ocean.context.ocean import ocean

from github.clients.auth import get_auth_provider
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.auth.github_app.installation_registry import (
    reset_authenticators_by_org,
)
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
from github.clients.http.base_client import AbstractGithubClient
from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.rest_client import GithubRestClient
from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry
from github.clients.utils import integration_config
from github.helpers.utils import GithubClientType

_CLIENT_CLASSES: Dict[GithubClientType, Type[AbstractGithubClient]] = {
    GithubClientType.REST: GithubRestClient,
    GithubClientType.GRAPHQL: GithubGraphQLClient,
}
_clients: Dict[tuple[str, GithubClientType], AbstractGithubClient] = {}


class GitHubAuthenticatorFactory:
    @staticmethod
    def create(
        github_host: str,
        organization: Optional[str] = None,
        token: Optional[str] = None,
        app_id: Optional[str] = None,
        installation_id: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> AbstractGitHubAuthenticator:
        if token:
            logger.debug(
                f"Creating Personal Token Authenticator for select organizations for PAT on {github_host}"
            )
            return PersonalTokenAuthenticator(token)

        if organization and app_id and private_key:
            logger.debug(
                f"Creating GitHub App Authenticator for {organization} on {github_host}"
            )
            return GitHubAppInstallationAuthenticator(
                app_auth=GitHubAppAuthenticator(
                    app_id=app_id,
                    private_key=private_key,
                    github_host=github_host,
                ),
                organization=organization,
                installation_id=installation_id,
            )

        raise MissingCredentials("No valid GitHub credentials provided.")


def _reset_after_fork() -> None:
    for client in _clients.values():
        client.authenticator._http_client = None
    _clients.clear()
    reset_authenticators_by_org()
    GitHubRateLimiterRegistry.reset_for_fork()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_after_fork)


def _get_client(
    authenticator: AbstractGitHubAuthenticator,
    client_type: GithubClientType = GithubClientType.REST,
) -> AbstractGithubClient:
    cache_key = (authenticator.rate_limit_scope, client_type)
    if cache_key not in _clients:
        logger.info(
            f"Instantiated new {client_type} client for scope {authenticator.rate_limit_scope}."
        )
        _clients[cache_key] = _CLIENT_CLASSES[client_type](
            **integration_config(authenticator),
        )
    return _clients[cache_key]


async def create_github_client_for_org(
    organization: str,
    client_type: GithubClientType = GithubClientType.REST,
) -> AbstractGithubClient:
    authenticator = await get_auth_provider().get_authenticator_for_organization(
        organization
    )
    return _get_client(authenticator, client_type or GithubClientType.REST)


@overload
def create_github_client(
    client_type: Literal[GithubClientType.REST],
) -> GithubRestClient: ...


@overload
def create_github_client(client_type: None = None) -> GithubRestClient: ...


@overload
def create_github_client(
    client_type: Literal[GithubClientType.GRAPHQL],
) -> GithubGraphQLClient: ...


def create_github_client(
    client_type: GithubClientType | None = GithubClientType.REST,
) -> AbstractGithubClient:
    """
    Legacy sync client factory for single-org PAT and GitHub App setups.

    Prefer create_github_client_for_org() for multi-org GitHub App usage.
    """
    config = ocean.integration_config
    authenticator = GitHubAuthenticatorFactory.create(
        github_host=config["github_host"],
        organization=config.get("github_organization"),
        token=config.get("github_token"),
        app_id=config.get("github_app_id"),
        installation_id=config.get("github_app_installation_id"),
        private_key=config.get("github_app_private_key"),
    )
    return _get_client(authenticator, client_type or GithubClientType.REST)
