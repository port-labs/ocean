"""Okta client factory for creating authenticated clients."""

from typing import Optional
from loguru import logger

from port_ocean.context.ocean import ocean
from okta.clients.http.client import OktaClient
from okta.helpers.exceptions import MissingIntegrationCredentialException


class OktaClientFactory:
    """Factory for creating Okta API clients."""

    _instance: Optional[OktaClient] = None

    @classmethod
    def get_client(cls) -> OktaClient:
        """Get or create a singleton Okta client instance.

        Returns:
            OktaClient instance
        """
        if cls._instance is None:
            cls._instance = cls.create_client()
        return cls._instance

    @classmethod
    def create_client(cls) -> OktaClient:
        """Create a new Okta client instance.

        Returns:
            New OktaClient instance
        """
        config = ocean.integration_config

        okta_domain = config.get("okta_domain")
        api_token = config.get("okta_api_token")

        if not okta_domain:
            raise MissingIntegrationCredentialException(
                "okta_domain is required in integration configuration"
            )
        if not api_token:
            raise MissingIntegrationCredentialException(
                "okta_api_token is required in integration configuration"
            )

        logger.info(f"Creating Okta client for domain: {okta_domain}")

        return OktaClient(
            okta_domain=okta_domain,
            api_token=api_token,
        )
