from github.clients.rest_client import GithubRestClient
from github.clients.base_client import AbstractGithubClient
from port_ocean.context.ocean import ocean
from loguru import logger


class GithubClientFactory:
    _instance = None
    _clients: dict[str, AbstractGithubClient] = {}

    def __new__(cls) -> "GithubClientFactory":
        if cls._instance is None:
            cls._instance = super(GithubClientFactory, cls).__new__(cls)
        return cls._instance

    def get_client(self, client_type: str) -> AbstractGithubClient:
        """Get or create a client instance from Ocean configuration.

        Args:
            client_type: Type of client to create ("rest" or other supported types)

        Returns:
            An instance of AbstractGithubClient

        Raises:
            ValueError: If client_type is invalid
        """
        if client_type not in self._clients:
            if client_type == "rest":
                self._clients[client_type] = GithubRestClient(
                    token=ocean.integration_config["github_token"],
                    organization=ocean.integration_config["github_organization"],
                    github_host=ocean.integration_config["github_host"],
                )
            else:
                logger.error(f"Invalid client type: {client_type}")
                raise ValueError(f"Invalid client type: {client_type}")
        return self._clients[client_type]


def create_github_client(client_type: str = "rest") -> AbstractGithubClient:
    factory = GithubClientFactory()
    return factory.get_client(client_type)
