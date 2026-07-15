import asyncio
import concurrent.futures
import os
from typing import Dict, Literal, Type, cast, overload

from loguru import logger
from github.helpers.exceptions import MissingCredentials
from port_ocean.context.ocean import ocean

from github.clients.auth import get_auth_provider
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.auth.github_app.installation_registry import (
    reset_authenticators_by_org,
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
    Create a GitHub client for the current organization.
    Notice: this function will be deprecated in favor of create_github_client_for_org
    in the future. for now it will keep same behavior of providing a multi-org client for PAT authentication,
    and a single-org client for GitHub App authentication.
    """
    if get_auth_provider().is_app_auth() and not ocean.integration_config.get(
        "github_organization"
    ):
        raise MissingCredentials("No valid GitHub credentials provided.")

    organization = cast(str, ocean.integration_config.get("github_organization") or "")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(
            asyncio.run,
            create_github_client_for_org(
                organization,
                client_type or GithubClientType.REST,
            ),
        ).result()
