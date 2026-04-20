from typing import Dict, Type
from enum import StrEnum

from loguru import logger
from port_ocean.context.ocean import ocean

from clickup.clients.auth.personal_token_authenticator import PersonalTokenAuthenticator
from clickup.clients.auth.abstract_authenticator import AbstractClickUpAuthenticator
from clickup.clients.http.clickup_client import ClickUpClient


class ClickUpClientType(StrEnum):
    """Supported ClickUp client types."""

    REST = "rest"


class ClickUpClientFactory:
    """Factory for creating ClickUp clients with singleton pattern."""

    _instance: "ClickUpClientFactory | None" = None
    _clients: Dict[ClickUpClientType, Type[ClickUpClient]] = {
        ClickUpClientType.REST: ClickUpClient
    }
    _instances: Dict[ClickUpClientType, ClickUpClient] = {}

    def __new__(cls) -> "ClickUpClientFactory":
        if cls._instance is None:
            cls._instance = super(ClickUpClientFactory, cls).__new__(cls)
        return cls._instance

    def get_client(self, client_type: ClickUpClientType) -> ClickUpClient:
        """Get or create a ClickUp client instance."""
        if client_type not in self._instances:
            if client_type not in self._clients:
                logger.error(f"Invalid client type: {client_type}")
                raise ValueError(f"Invalid client type: {client_type}")

            authenticator = PersonalTokenAuthenticator(
                ocean.integration_config["clickup_api_token"]
            )
            self._instances[client_type] = self._clients[client_type](
                **_integration_config(authenticator),
            )

            logger.info(f"Created new ClickUp {client_type} client")

        return self._instances[client_type]

    @classmethod
    def clear(cls) -> None:
        """Clear all cached client instances."""
        cls._instances = {}


def _integration_config(authenticator: AbstractClickUpAuthenticator) -> Dict[str, str]:
    """Build integration config for client initialization."""
    return {
        "authenticator": authenticator,
        "base_url": ocean.integration_config.get(
            "clickup_api_base_url", "https://api.clickup.com/api"
        ),
    }


def create_clickup_client(
    client_type: ClickUpClientType = ClickUpClientType.REST,
) -> ClickUpClient:
    """Create a ClickUp client using the factory."""
    factory = ClickUpClientFactory()
    return factory.get_client(client_type)
