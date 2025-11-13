"""Harbor Client Initialization Module."""

from harbor.config.app_config import get_harbor_config
from harbor.client.harbor_client import HarborClient

_client_instance: HarborClient | None = None


def get_harbor_client() -> HarborClient:
    """Initialize and return a configured Harbor client.

    Creates a Harbor client using configuration from ocean.integration_config.
    Subsequent calls return the cached instance.

    Returns:
        HarborClient: Configured Harbor API client instance

    Raises:
        ValueError: If required configuration is missing
    """

    global _client_instance

    if _client_instance is not None:
        return _client_instance
    
    harbor_url, username, password, verify_ssl = get_harbor_config()   

    _client_instance = HarborClient(
        harbor_url=str(harbor_url),
        username=str(username),
        password=str(password),
        verify_ssl=bool(verify_ssl),
    )

    return _client_instance
