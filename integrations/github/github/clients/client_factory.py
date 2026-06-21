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
    for client in GithubClientFactory._instances.values():
        client.authenticator._http_client = None
    for client in GithubClientFactory._per_org_clients.values():
        client.authenticator._http_client = None
    GithubClientFactory._instances.clear()
    GithubClientFactory._per_org_clients.clear()
    GithubClientFactory._installation_map.clear()
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
    _instances: Dict[GithubClientType, AbstractGithubClient] = {}
    _per_org_clients: Dict[tuple[GithubClientType, str], AbstractGithubClient] = {}
    _installation_map: Dict[str, str] = {}  # org_login -> installation_id

    def __new__(cls) -> "GithubClientFactory":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def _is_app_multi_org(self) -> bool:
        cfg = ocean.integration_config
        return bool(
            cfg.get("github_app_id")
            and cfg.get("github_app_private_key")
            and not cfg.get("github_organization")
            and not cfg.get("github_app_installation_id")
        )

    def get_client(
        self,
        client_type: GithubClientType,
        *,
        org_login: Optional[str] = None,
        installation_id: Optional[str] = None,
    ) -> AbstractGithubClient:
        if client_type not in self._clients:
            raise ValueError(f"Invalid client type: {client_type}")

        resolved_installation_id = installation_id or (
            self._installation_map.get(org_login) if org_login else None
        )

        if org_login and resolved_installation_id:
            return self._get_per_org_client(client_type, org_login, resolved_installation_id)

        return self._get_default_client(client_type, org_login)

    def _get_per_org_client(
        self,
        client_type: GithubClientType,
        org_login: str,
        installation_id: str,
    ) -> AbstractGithubClient:
        key = (client_type, org_login)
        if key not in self._per_org_clients:
            cfg = ocean.integration_config
            authenticator = GitHubAppAuthenticator(
                app_id=cfg["github_app_id"],
                private_key=cfg["github_app_private_key"],
                organization=org_login,
                installation_id=installation_id,
                github_host=cfg["github_host"],
            )
            logger.info(f"Creating per-org {client_type} client for {org_login}.")
            self._per_org_clients[key] = self._clients[client_type](
                **integration_config(authenticator)
            )
        return self._per_org_clients[key]

    def _get_default_client(
        self,
        client_type: GithubClientType,
        org_login: Optional[str] = None,
    ) -> AbstractGithubClient:
        if client_type not in self._instances:
            cfg = ocean.integration_config
            authenticator = GitHubAuthenticatorFactory.create(
                github_host=cfg["github_host"],
                organization=org_login or cfg.get("github_organization"),
                token=cfg.get("github_token"),
                app_id=cfg.get("github_app_id"),
                installation_id=cfg.get("github_app_installation_id"),
                private_key=cfg.get("github_app_private_key"),
            )
            logger.info(f"Creating {client_type} client.")
            self._instances[client_type] = self._clients[client_type](
                **integration_config(authenticator)
            )
        return self._instances[client_type]

    async def _discover_installations(self) -> None:
        """Populate _installation_map via JWT by listing all app installations."""
        cfg = ocean.integration_config
        authenticator = GitHubAppAuthenticator(
            app_id=cfg["github_app_id"],
            private_key=cfg["github_app_private_key"],
            github_host=cfg["github_host"],
        )
        async for page in authenticator.list_installations():
            for installation in page:
                login = installation.get("account", {}).get("login", "")
                if login:
                    self._installation_map[login] = str(installation["id"])

    async def iter_org_clients(
        self,
        client_type: GithubClientType = GithubClientType.REST,
        *,
        allowed_orgs: Optional[List[str]] = None,
    ) -> AsyncGenerator[tuple[AbstractGithubClient, Optional[str]], None]:
        """Yield one (client, org_name) pair per organisation.

        App multi-org: one scoped client per installation, filtered by allowed_orgs.
        All other modes: a single (default_client, None) pair.
        """
        if not self._is_app_multi_org:
            yield self.get_client(client_type), None
            return

        if not self._installation_map:
            await self._discover_installations()

        for org_login in list(self._installation_map):
            if allowed_orgs and org_login not in allowed_orgs:
                continue
            yield self.get_client(client_type, org_login=org_login), org_login


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
