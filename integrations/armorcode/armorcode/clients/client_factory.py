from typing import Dict, Type, Any
from loguru import logger
from enum import StrEnum

from port_ocean.context.ocean import ocean
from armorcode.clients.auth.api_key_authenticator import ApiKeyAuthenticator
from armorcode.clients.http.armorcode_client import ArmorcodeClient
from armorcode.clients.auth.abstract_authenticator import AbstractArmorcodeAuthenticator


class ArmorcodeClientType(StrEnum):
    """Supported ArmorCode client types."""

    REST = "rest"


class ArmorcodeClientFactory:
    """Factory for creating ArmorCode clients."""

    _instance = None
    _clients: Dict[ArmorcodeClientType, Type[ArmorcodeClient]] = {
        ArmorcodeClientType.REST: ArmorcodeClient
    }
    _instances: Dict[ArmorcodeClientType, ArmorcodeClient] = {}

    def __new__(cls) -> "ArmorcodeClientFactory":
        if cls._instance is None:
            cls._instance = super(ArmorcodeClientFactory, cls).__new__(cls)
        return cls._instance

    def get_client(self, client_type: ArmorcodeClientType) -> ArmorcodeClient:
        """Get or create an ArmorCode client instance."""
        if client_type not in self._instances:
            if client_type not in self._clients:
                logger.error(f"Invalid client type: {client_type}")
                raise ValueError(f"Invalid client type: {client_type}")

            authenticator = ApiKeyAuthenticator(
                ocean.integration_config["armorcode_api_key"]
            )
            self._instances[client_type] = self._clients[client_type](
                **integration_config(authenticator),
            )

            logger.info(f"Created new ArmorCode {client_type} client")

        return self._instances[client_type]


def integration_config(authenticator: AbstractArmorcodeAuthenticator) -> Dict[str, Any]:
    return {
        "authenticator": authenticator,
        "base_url": ocean.integration_config["armorcode_api_base_url"],
    }


def create_armorcode_client(
    client_type: ArmorcodeClientType = ArmorcodeClientType.REST,
) -> ArmorcodeClient:
    """Create an ArmorCode client using the factory."""
    factory = ArmorcodeClientFactory()
    return factory.get_client(client_type)
