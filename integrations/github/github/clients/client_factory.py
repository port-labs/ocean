import os
from typing import Dict, Literal, Type, cast, overload

from loguru import logger
from github.clients.auth import get_auth_provider
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.auth.github_app.installation_registry import (
    reset_authenticators_by_org,
)
from github.clients.http.base_client import AbstractGithubClient
from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.rest_client import GithubRestClient
from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry
from github.clients.utils import integration_config
from github.helpers.exceptions import OrganizationRequiredException
from github.helpers.utils import GithubClientType
from port_ocean.context.ocean import ocean

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


async def resolve_discovery_organization() -> str:
    """Pick an organization for org-discovery calls before a specific org is known."""
    if org := ocean.integration_config.get("github_organization"):
        return org

    from integration import GithubPortAppConfig
    from port_ocean.context.event import event

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    if orgs := port_app_config.organizations:
        return orgs[0]

    auth_provider = get_auth_provider()
    if auth_provider.is_app_auth():
        authenticators = await auth_provider.list_authenticators()
        installation_auth = authenticators[0]
        if isinstance(installation_auth, GitHubAppInstallationAuthenticator):
            return installation_auth.organization
        raise OrganizationRequiredException(
            "No GitHub App installation found for org-discovery"
        )

    raise OrganizationRequiredException(
        "Organization is required for org-discovery when using non-classic PAT tokens"
    )


@overload
async def create_github_client_for_discovery(
    client_type: Literal[GithubClientType.REST] = GithubClientType.REST,
) -> GithubRestClient: ...


@overload
async def create_github_client_for_discovery(
    client_type: Literal[GithubClientType.GRAPHQL],
) -> GithubGraphQLClient: ...


async def create_github_client_for_discovery(
    client_type: GithubClientType = GithubClientType.REST,
) -> AbstractGithubClient:
    organization = await resolve_discovery_organization()
    if client_type == GithubClientType.GRAPHQL:
        return await create_github_client_for_org(
            organization, GithubClientType.GRAPHQL
        )
    return await create_github_client_for_org(organization)


@overload
async def create_github_client_for_org(
    organization: str,
    client_type: Literal[GithubClientType.GRAPHQL],
) -> GithubGraphQLClient: ...


@overload
async def create_github_client_for_org(
    organization: str,
    client_type: Literal[GithubClientType.REST] = GithubClientType.REST,
) -> GithubRestClient: ...


async def create_github_client_for_org(
    organization: str,
    client_type: GithubClientType = GithubClientType.REST,
) -> AbstractGithubClient:
    authenticator = await get_auth_provider().get_authenticator_for_organization(
        organization
    )
    return _get_client(authenticator, client_type or GithubClientType.REST)
