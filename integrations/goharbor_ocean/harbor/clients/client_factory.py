"""Harbor client factory for creating authenticated clients."""

from typing import Optional

from loguru import logger
from port_ocean.context.ocean import ocean

from harbor.clients.http.client import HarborClient
from harbor.helpers.exceptions import InvalidConfigurationError, MissingCredentialsError


class HarborClientFactory:
    """Factory for creating Harbor API clients."""

    _instance: Optional[HarborClient] = None

    @classmethod
    def get_client(cls) -> HarborClient:
        """Get or create a singleton Harbor client instance."""
        if cls._instance is None:
            cls._instance = cls.create_client()
        return cls._instance

    @classmethod
    def create_client(cls) -> HarborClient:
        """Create a new Harbor client instance.

        Returns:
            New HarborClient instance

        Raises:
            InvalidConfigurationError: If harbor_url is missing
            MissingCredentialsError: If credentials are missing
        """
        config = ocean.integration_config

        harbor_url = config.get("harbor_url")
        harbor_username = config.get("harbor_username")
        harbor_password = config.get("harbor_password")

        if not harbor_url:
            raise InvalidConfigurationError("harbor_url is required in integration configuration")

        if not harbor_username:
            raise MissingCredentialsError("harbor_username is required in integration configuration")

        if not harbor_password:
            raise MissingCredentialsError("harbor_password is required in integration configuration")

        logger.info(f"Creating Harbor client for: {harbor_url}")

        return HarborClient(
            base_url=harbor_url,
            username=harbor_username,
            password=harbor_password,
        )
