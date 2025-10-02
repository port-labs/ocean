from typing import Optional
from loguru import logger

from armorcode.clients.auth.api_key_authenticator import ApiKeyAuthenticator
from armorcode.clients.http.armorcode_client import ArmorcodeClient


class ArmorcodeClientType:
    """Supported ArmorCode client types."""

    REST: str = "rest"


class ArmorcodeClientFactory:
    """Factory for creating ArmorCode clients."""

    _instance: Optional["ArmorcodeClientFactory"] = None
    _initialized: bool = False

    def __new__(cls) -> "ArmorcodeClientFactory":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._instances: dict[str, ArmorcodeClient] = {}
            self._initialized = True

    def get_client(
        self,
        client_type: str,
        base_url: str,
        api_key: str,
    ) -> ArmorcodeClient:
        """Get or create an ArmorCode client instance."""
        if client_type not in self._instances:
            authenticator = ApiKeyAuthenticator(api_key)
            self._instances[client_type] = ArmorcodeClient(base_url, authenticator)
            logger.info(f"Created new ArmorCode {client_type} client")

        return self._instances[client_type]


def create_armorcode_client(
    base_url: str,
    api_key: str,
    client_type: str = ArmorcodeClientType.REST,
) -> ArmorcodeClient:
    """Create an ArmorCode client using the factory."""
    factory = ArmorcodeClientFactory()
    return factory.get_client(client_type, base_url, api_key)
