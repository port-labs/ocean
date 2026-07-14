import asyncio
import concurrent.futures
import os
from collections.abc import Coroutine
from typing import Any, Dict, Literal, Type, TypeVar, cast, overload

from loguru import logger
from port_ocean.context.ocean import ocean

from github.clients.auth.auth_backend import (
    get_authenticator_for_organization,
    get_integration_actor,
)
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.auth.github_app.installation_registry import (
    reset_authenticators_by_org,
)
from github.clients.auth.personal_access_token_authenticator import (
    reset_pat_instances,
)
from github.clients.http.base_client import AbstractGithubClient
from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.rest_client import GithubRestClient
from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry
from github.clients.utils import integration_config
from github.helpers.utils import GithubClientType

T = TypeVar("T")

_CLIENT_CLASSES: Dict[GithubClientType, Type[AbstractGithubClient]] = {
    GithubClientType.REST: GithubRestClient,
    GithubClientType.GRAPHQL: GithubGraphQLClient,
}
_clients: Dict[tuple[str, GithubClientType], AbstractGithubClient] = {}


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def _reset_after_fork() -> None:
    for client in _clients.values():
        client.authenticator._http_client = None
    _clients.clear()
    reset_authenticators_by_org()
    reset_pat_instances()
    GitHubRateLimiterRegistry.reset_for_fork()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_after_fork)


def get_github_client(
    authenticator: AbstractGitHubAuthenticator, client_type: GithubClientType
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


async def get_authenticated_actor() -> str:
    return await get_integration_actor()


@overload
def create_github_client_for_org(
    organization: str | None,
    client_type: Literal[GithubClientType.REST],
) -> GithubRestClient: ...


@overload
def create_github_client_for_org(
    organization: str | None,
    client_type: None = None,
) -> GithubRestClient: ...


@overload
def create_github_client_for_org(
    organization: str | None,
    client_type: Literal[GithubClientType.GRAPHQL],
) -> GithubGraphQLClient: ...


@overload
def create_github_client_for_org(
    organization: str | None,
    client_type: GithubClientType,
) -> AbstractGithubClient: ...


def create_github_client_for_org(
    organization: str | None,
    client_type: GithubClientType | None = GithubClientType.REST,
) -> AbstractGithubClient:
    authenticator = _run_async(get_authenticator_for_organization(organization))
    return get_github_client(authenticator, client_type or GithubClientType.REST)


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
    organization = cast(str | None, ocean.integration_config.get("github_organization"))
    return create_github_client_for_org(
        organization, client_type or GithubClientType.REST
    )
