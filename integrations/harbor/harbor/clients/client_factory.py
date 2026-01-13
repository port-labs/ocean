"""Harbor client factory for creating authenticated clients."""

from typing import Optional

from loguru import logger
from port_ocean.context.ocean import ocean

from harbor.clients.http.client import HarborClient
from harbor.helpers.exceptions import MissingIntegrationCredentialException


class HarborClientFactory:
    """Factory for creating Harbor API clients."""

    _instance: Optional[HarborClient] = None

    @classmethod
    def get_client(cls) -> HarborClient:
        """Get or create a singleton Harbor client instance.

        Returns:
            HarborClient instance
        """
        if cls._instance is None:
            cls._instance = cls.create_client()
        return cls._instance

    @classmethod
    def create_client(cls) -> HarborClient:
        """Create a new Harbor client instance.

        Returns:
            New HarborClient instance
        """
        config = ocean.integration_config

        base_url = config.get("base_url")
        username = config.get("username")
        password = config.get("password")
        api_version = config.get("api_version", "v2.0")

        if not base_url:
            raise MissingIntegrationCredentialException(
                "base_url is required in integration configuration"
            )
        if not username:
            raise MissingIntegrationCredentialException(
                "username is required in integration configuration"
            )
        if not password:
            raise MissingIntegrationCredentialException(
                "password is required in integration configuration"
            )

        logger.info(f"Creating Harbor client for base URL: {base_url}")

        return HarborClient(
            base_url=base_url,
            username=username,
            password=password,
            api_version=api_version,
        )

    @classmethod
    def reset_client(cls) -> None:
        """Reset the singleton client instance.

        This is primarily useful for testing or when configuration changes
        require a new client instance.
        """
        cls._instance = None

