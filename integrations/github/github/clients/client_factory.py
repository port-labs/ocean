import os
from dataclasses import dataclass
from typing import Dict, Literal, Type, overload

from loguru import logger
from port_ocean.context.ocean import ocean

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    AuthScope,
)
from github.clients.auth.githuba_app.github_app_installation_registry import (
    GitHubAppInstallationRegistry,
    reset_installation_index,
)
from github.clients.auth.githuba_app.github_app_jwt_client import GitHubAppJwtClient
from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
    reset_pat_instances,
)
from github.clients.http.base_client import AbstractGithubClient
from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.rest_client import GithubRestClient
from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry
from github.clients.utils import integration_config
from github.helpers.exceptions import MissingCredentials
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


async def _list_auth_scopes() -> list[AuthScope]:
    config = ocean.integration_config
    if config.get("github_token"):
        return await PersonalTokenAuthenticator.list_scopes(config)
    if config.get("github_app_id") and config.get("github_app_private_key"):
        return await GitHubAppInstallationRegistry.list_scopes(config)
    raise MissingCredentials("No valid GitHub credentials provided.")


def _authenticator_for_org(organization: str | None) -> AbstractGitHubAuthenticator:
    config = ocean.integration_config
    if config.get("github_token"):
        return PersonalTokenAuthenticator.for_org(config, organization)
    if config.get("github_app_id") and config.get("github_app_private_key"):
        if organization is None:
            raise MissingCredentials(
                "Organization is required for GitHub App authentication."
            )
        return GitHubAppInstallationRegistry.for_org(config, organization)
    raise MissingCredentials("No valid GitHub credentials provided.")


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
    config = ocean.integration_config
    if config.get("github_token"):
        authenticator = PersonalTokenAuthenticator.for_org(config, None)
    if config.get("github_app_id") and config.get("github_app_private_key"):
        authenticator = GitHubAppJwtClient.from_config(config)

    if not authenticator:
        raise MissingCredentials("No valid GitHub credentials provided.")
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
