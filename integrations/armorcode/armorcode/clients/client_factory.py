from loguru import logger

from .auth.api_key_authenticator import ApiKeyAuthenticator
from .http.armorcode_client import ArmorcodeClient


class ArmorcodeClientType:
    """Supported ArmorCode client types."""

    REST: str = "rest"


class ArmorcodeClientFactory:
    """Factory for creating ArmorCode clients."""

    def __init__(self) -> None:
        self._instances: dict[str, ArmorcodeClient] = {}

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


# Global factory instance
_client_factory = ArmorcodeClientFactory()


def create_armorcode_client(
    base_url: str,
    api_key: str,
    client_type: str = ArmorcodeClientType.REST,
) -> ArmorcodeClient:
    """Create an ArmorCode client using the factory."""
    return _client_factory.get_client(client_type, base_url, api_key)
