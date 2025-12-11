from harbor.clients.http.harbor_client import HarborClient
from harbor.clients.auth.auth_factory import HarborAuthenticatorFactory
from harbor.helpers.exceptions import MissingConfiguration
from port_ocean.context.ocean import ocean
from loguru import logger


class HarborClientFactory:
    """Factory for creating Harbor client instances"""

    _instance = None
    _client_instance: HarborClient | None = None

    def __new__(cls) -> "HarborClientFactory":
        if cls._instance is None:
            cls._instance = super(HarborClientFactory, cls).__new__(cls)
        return cls._instance

    def get_client(self) -> HarborClient:
        """Get or create a Harbor client instance from Ocean configuration.

        Returns:
            An instance of HarborClient
        """
        if self._client_instance is None:
            config = ocean.integration_config

            authenticator = HarborAuthenticatorFactory.create(
                harbor_host=config.get("harbor_host"),
                username=config.get("username"),
                password=config.get("password"),
                robot_name=config.get("robot_name"),
                robot_token=config.get("robot_token"),
            )

            harbor_host = config.get("harbor_host")
            if not harbor_host:
                logger.error("harbor_host is required in configuration")
                raise MissingConfiguration("harbor_host is required in configuration")

            self._client_instance = HarborClient(
                harbor_host=harbor_host,
                authenticator=authenticator,
            )

        return self._client_instance


def init_client() -> HarborClient:
    """Initialize Harbor client from Ocean configuration using factory pattern."""
    factory = HarborClientFactory()
    return factory.get_client()
