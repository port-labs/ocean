import os
from dataclasses import dataclass
from typing import Dict, Literal, Optional, Type, overload

from loguru import logger
from port_ocean.context.ocean import ocean

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    AuthScope,
)
from github.clients.auth.auth_backend import GitHubAuthBackend, resolve_auth_backend
from github.clients.auth.github_app_installation_registry import (
    reset_installation_index,
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

_CLIENT_CLASSES: Dict[GithubClientType, Type[AbstractGithubClient]] = {
    GithubClientType.REST: GithubRestClient,
    GithubClientType.GRAPHQL: GithubGraphQLClient,
}
_clients: Dict[tuple[str, GithubClientType], AbstractGithubClient] = {}


def _reset_after_fork() -> None:
    for client in _clients.values():
        client.authenticator._http_client = None
    _clients.clear()
    reset_installation_index()
    reset_pat_instances()
    GitHubRateLimiterRegistry.reset_for_fork()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_after_fork)


@dataclass(frozen=True)
class GithubClientScope:
    organization: str | None
    account_type: str | None
    installation_id: str | None
    authenticator: AbstractGitHubAuthenticator

    @overload
    def get_client(
        self, client_type: Literal[GithubClientType.REST]
    ) -> GithubRestClient: ...

    @overload
    def get_client(
        self, client_type: Literal[GithubClientType.GRAPHQL]
    ) -> GithubGraphQLClient: ...

    def get_client(self, client_type: GithubClientType) -> AbstractGithubClient:
        return _client_for(self.authenticator, client_type)


def _auth_backend() -> type[GitHubAuthBackend]:
    return resolve_auth_backend(ocean.integration_config)


async def _list_auth_scopes() -> list[AuthScope]:
    backend = _auth_backend()
    return await backend.list_scopes(ocean.integration_config)


def _authenticator_for_org(organization: str | None) -> AbstractGitHubAuthenticator:
    backend = _auth_backend()
    return backend.for_org(ocean.integration_config, organization)


def _client_for(
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


def _to_client_scope(scope: AuthScope) -> GithubClientScope:
    return GithubClientScope(
        scope.organization,
        scope.account_type,
        scope.installation_id,
        scope.authenticator,
    )


async def create_github_clients() -> list[GithubClientScope]:
    return [_to_client_scope(scope) for scope in await _list_auth_scopes()]


async def get_authenticated_actor() -> str:
    backend = _auth_backend()
    authenticator = backend.for_actor(ocean.integration_config)
    return await authenticator.get_authenticated_actor()


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


def create_github_client_for_org(
    organization: str | None,
    client_type: GithubClientType | None = GithubClientType.REST,
) -> AbstractGithubClient:
    return _client_for(
        _authenticator_for_org(organization), client_type or GithubClientType.REST
    )


class GitHubAuthenticatorFactory:
    """Backward-compatible factory for webhook setup until main.py is migrated."""

    @staticmethod
    def create(
        github_host: str,
        organization: Optional[str] = None,
        token: Optional[str] = None,
        app_id: Optional[str] = None,
        installation_id: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> AbstractGitHubAuthenticator:
        del github_host, token, app_id, installation_id, private_key
        return _authenticator_for_org(organization)


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
    client_type: GithubClientType | None = None,
) -> AbstractGithubClient:
    organization = ocean.integration_config.get("github_organization")
    resolved = client_type or GithubClientType.REST
    return create_github_client_for_org(organization, resolved)
