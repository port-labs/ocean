import os
from typing import AsyncGenerator, Dict, List, Optional, Type, overload, Literal

from port_ocean.context.ocean import ocean
from github.clients.http.rest_client import GithubRestClient
from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.base_client import AbstractGithubClient
from loguru import logger
from github.helpers.utils import GithubClientType
from github.clients.utils import integration_config

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
from github.clients.auth.github_app_authenticator import GitHubAppAuthenticator
from github.helpers.exceptions import MissingCredentials
from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry


def _reset_clients_after_fork() -> None:
    """Clear cached clients after fork so children create fresh httpx connections
    and asyncio primitives (Semaphore, Lock) that are bound to the parent's event loop.
    """
    if GithubClientFactory._auth_instance is not None:
        GithubClientFactory._auth_instance._http_client = None
    for client in GithubClientFactory._instances.values():
        client.authenticator._http_client = None
    for client in GithubClientFactory._per_org_clients.values():
        client.authenticator._http_client = None
    GithubClientFactory._auth_instance = None
    GithubClientFactory._instances.clear()
    GithubClientFactory._per_org_clients.clear()
    GitHubRateLimiterRegistry.reset_for_fork()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_clients_after_fork)


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

        if app_id and private_key:
            logger.debug(
                f"Creating GitHub App Authenticator for {organization or 'all installations'} on {github_host}"
            )
            return GitHubAppAuthenticator(
                app_id=app_id,
                installation_id=installation_id,
                private_key=private_key,
                organization=organization,
                github_host=github_host,
            )

        raise MissingCredentials("No valid GitHub credentials provided.")


class GithubClientFactory:
    _instance: Optional["GithubClientFactory"] = None
    _clients: Dict[GithubClientType, Type[AbstractGithubClient]] = {
        GithubClientType.REST: GithubRestClient,
        GithubClientType.GRAPHQL: GithubGraphQLClient,
    }
    _auth_instance: Optional[AbstractGitHubAuthenticator] = None
    _instances: Dict[GithubClientType, AbstractGithubClient] = {}
    _per_org_clients: Dict[
        tuple[GithubClientType, Optional[str]], AbstractGithubClient
    ] = {}

    def __new__(cls) -> "GithubClientFactory":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def _authenticator(self) -> AbstractGitHubAuthenticator:
        if GithubClientFactory._auth_instance is None:
            cfg = ocean.integration_config
            GithubClientFactory._auth_instance = GitHubAuthenticatorFactory.create(
                github_host=cfg["github_host"],
                organization=cfg.get("github_organization"),
                token=cfg.get("github_token"),
                app_id=cfg.get("github_app_id"),
                installation_id=cfg.get("github_app_installation_id"),
                private_key=cfg.get("github_app_private_key"),
            )
        return GithubClientFactory._auth_instance

    def _get_or_create_org_client(
        self,
        client_type: GithubClientType,
        authenticator: AbstractGitHubAuthenticator,
    ) -> AbstractGithubClient:
        org_name = authenticator.organization
        key: tuple[GithubClientType, Optional[str]] = (client_type, org_name)
        if key not in self._per_org_clients:
            if org_name:
                logger.info(f"Creating {client_type} client for org {org_name}.")
            self._per_org_clients[key] = self._clients[client_type](
                **integration_config(authenticator)
            )
        return self._per_org_clients[key]

    def _get_default_client(
        self, client_type: GithubClientType
    ) -> AbstractGithubClient:
        if client_type not in self._instances:
            logger.info(f"Creating {client_type} client.")
            self._instances[client_type] = self._clients[client_type](
                **integration_config(self._authenticator)
            )
        return self._instances[client_type]

    def get_client(
        self,
        client_type: GithubClientType,
        *,
        org_login: Optional[str] = None,
        installation_id: Optional[str] = None,
    ) -> AbstractGithubClient:
        if client_type not in self._clients:
            raise ValueError(f"Invalid client type: {client_type}")
        if org_login:
            authenticator = self._authenticator.create_org_scoped_authenticator(
                org_login, installation_id or ""
            )
            return self._get_or_create_org_client(client_type, authenticator)
        return self._get_default_client(client_type)

    async def iter_org_clients(
        self,
        client_type: GithubClientType = GithubClientType.REST,
        *,
        allowed_orgs: Optional[List[str]] = None,
    ) -> AsyncGenerator[tuple[AbstractGithubClient, Optional[str]], None]:
        """Yield one (client, org_name) pair per accessible organisation."""
        async for authenticator in self._authenticator.iter_org_authenticators(allowed_orgs):
            client = self._get_or_create_org_client(client_type, authenticator)
            yield client, authenticator.organization


@overload
def create_github_client(
    client_type: Literal[GithubClientType.REST] = ...,
    *,
    org_login: Optional[str] = None,
    installation_id: Optional[str] = None,
) -> GithubRestClient: ...


@overload
def create_github_client(
    client_type: None,
    *,
    org_login: Optional[str] = None,
    installation_id: Optional[str] = None,
) -> GithubRestClient: ...


@overload
def create_github_client(
    client_type: Literal[GithubClientType.GRAPHQL],
    *,
    org_login: Optional[str] = None,
    installation_id: Optional[str] = None,
) -> GithubGraphQLClient: ...


def create_github_client(
    client_type: GithubClientType | None = GithubClientType.REST,
    *,
    org_login: Optional[str] = None,
    installation_id: Optional[str] = None,
) -> AbstractGithubClient:
    return GithubClientFactory().get_client(
        client_type or GithubClientType.REST,
        org_login=org_login,
        installation_id=installation_id,
    )
