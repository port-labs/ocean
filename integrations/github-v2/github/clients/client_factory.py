from typing import Any, Dict, Type
from github.clients.rest_client import GithubRestClient
from github.clients.graphql_client import GithubGraphQLClient
from github.clients.base_client import AbstractGithubClient
from port_ocean.context.ocean import ocean
from loguru import logger
from github.helpers.utils import GithubClientType
from github.webhook.webhook_client import GithubWebhookClient


class GithubClientFactory:
    _instance = None
    _clients: Dict[GithubClientType, Type[AbstractGithubClient]] = {
        GithubClientType.REST: GithubRestClient,
        GithubClientType.GRAPHQL: GithubGraphQLClient,
        GithubClientType.WEBHOOK: GithubWebhookClient,
    }
    _instances: Dict[GithubClientType, AbstractGithubClient] = {}

    def __new__(cls) -> "GithubClientFactory":
        if cls._instance is None:
            cls._instance = super(GithubClientFactory, cls).__new__(cls)
        return cls._instance

    def get_client(
        self, client_type: GithubClientType, **kwargs: Any
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

            self._instances[client_type] = self._clients[client_type](
                token=ocean.integration_config["github_token"],
                organization=ocean.integration_config["github_organization"],
                github_host=ocean.integration_config["github_host"],
                **kwargs,
            )

        return self._instances[client_type]


def create_github_client(
    client_type: GithubClientType | None = GithubClientType.REST, **kwargs: Any
) -> AbstractGithubClient:
    factory = GithubClientFactory()
    return factory.get_client(client_type or GithubClientType.REST, **kwargs)
