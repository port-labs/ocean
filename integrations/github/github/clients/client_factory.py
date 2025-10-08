from typing import Dict, Type, overload, Literal, Optional

from port_ocean.context.ocean import ocean
from github.clients.http.rest_client import GithubRestClient
from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.base_client import AbstractGithubClient
from github.clients.http.organization_client import OrganizationGithubClient
from loguru import logger
from github.helpers.utils import GithubClientType
from github.clients.utils import integration_config

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.auth.personal_access_token_authenticator import (
    PersonalTokenAuthenticator,
)
from github.clients.auth.github_app_authenticator import GitHubAppAuthenticator
from github.helpers.exceptions import MissingCredentials


class GitHubAuthenticatorFactory:
    @staticmethod
    def create(
        github_host: str,
        organization: Optional[str],
        token: Optional[str] = None,
        app_id: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> AbstractGitHubAuthenticator:
        if token:
            logger.debug(
                f"Creating Personal Token Authenticator for {organization or 'select organizations for PAT'} on {github_host}"
            )
            return PersonalTokenAuthenticator(token)

        if organization and app_id and private_key:
            logger.debug(
                f"Creating GitHub App Authenticator for {organization} on {github_host}"
            )
            return GitHubAppAuthenticator(
                app_id=app_id,
                private_key=private_key,
                organization=organization,
                github_host=github_host,
            )

        raise MissingCredentials("No valid GitHub credentials provided.")


class GithubClientFactory:
    _instance = None
    _clients: Dict[GithubClientType, Type[AbstractGithubClient]] = {
        GithubClientType.REST: GithubRestClient,
        GithubClientType.GRAPHQL: GithubGraphQLClient,
    }
    _instances: Dict[GithubClientType, AbstractGithubClient] = {}

    def __new__(cls) -> "GithubClientFactory":
        if cls._instance is None:
            cls._instance = super(GithubClientFactory, cls).__new__(cls)
        return cls._instance

    def get_client(
        self, github_organization: str, client_type: GithubClientType
    ) -> AbstractGithubClient:
        """Get or create a client instance from Ocean configuration.

        Args:
            client_type: Type of client to create ("rest" or other supported types)

        Returns:
            An instance of AbstractGithubClient

        Raises:
            ValueError: If client_type is invalid
        """

        if client_type not in self._instances:
            if client_type not in self._clients:
                logger.error(f"Invalid client type: {client_type}")
                raise ValueError(f"Invalid client type: {client_type}")

            logger.info(f"Creating new {client_type} client for organization: {github_organization}")
            authenticator = GitHubAuthenticatorFactory.create(
                organization=github_organization,
                github_host=ocean.integration_config["github_host"],
                token=ocean.integration_config.get("github_token"),
                app_id=ocean.integration_config.get("github_app_id"),
                private_key=ocean.integration_config.get("github_app_private_key"),
            )

            self._instances[client_type] = self._clients[client_type](
                **integration_config(authenticator, github_organization),
            )
            logger.info(f"Created and cached {client_type} client for {github_organization}")
        else:
            logger.debug(f"Using cached {client_type} client for organization: {github_organization}")

        return self._instances[client_type]

    def clear_instances(self) -> None:
        """Clear all cached client instances from memory."""
        logger.info(f"Clearing {len(self._instances)} cached GitHub client instances")
        self._instances.clear()


@overload
def create_github_client(
    github_organization: str,
    client_type: Literal[GithubClientType.REST],
) -> GithubRestClient: ...


@overload
def create_github_client(
    github_organization: str, client_type: None = None
) -> GithubRestClient: ...


@overload
def create_github_client(
    github_organization: str,
    client_type: Literal[GithubClientType.GRAPHQL],
) -> GithubGraphQLClient: ...


def create_github_client(
    github_organization: str,
    client_type: GithubClientType | None = GithubClientType.REST,
) -> AbstractGithubClient:
    factory = GithubClientFactory()
    return factory.get_client(github_organization, client_type or GithubClientType.REST)


def create_client_for_organizations() -> OrganizationGithubClient:
    return OrganizationGithubClient(
        github_host=ocean.integration_config["github_host"],
        authenticator=GitHubAuthenticatorFactory.create(
            organization=None,
            github_host=ocean.integration_config["github_host"],
            token=ocean.integration_config.get("github_token"),
            app_id=ocean.integration_config.get("github_app_id"),
            private_key=ocean.integration_config.get("github_app_private_key"),
        ),
    )


def clear_github_clients() -> None:
    """Clear all cached GitHub client instances from memory."""
    factory = GithubClientFactory()
    factory.clear_instances()
