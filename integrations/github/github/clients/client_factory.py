from typing import Dict, Type, overload, Literal
from github.clients.rest_client import GithubRestClient
from github.clients.graphql_client import GithubGraphQLClient
from github.clients.base_client import AbstractGithubClient
from loguru import logger
from github.helpers.utils import GithubClientType
from github.clients.utils import integration_config


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

    def get_client(self, client_type: GithubClientType) -> AbstractGithubClient:
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

            self._instances[client_type] = self._clients[client_type](
                **integration_config(),
            )

        return self._instances[client_type]


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
    factory = GithubClientFactory()
    return factory.get_client(client_type or GithubClientType.REST)
