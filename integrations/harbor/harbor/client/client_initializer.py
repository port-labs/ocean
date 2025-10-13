"""Harbor Client Initialization Module."""

from port_ocean.context.ocean import ocean
from harbor.client.harbor_client import HarborClient


def init_harbor_client() -> HarborClient:
    """Initialize and return a configured Harbor client.

    Reads configuration from ocean.integration_config and creates a client
    instance with the necessary authentication and connection parameters.

    Returns:
        HarborClient: Configured Harbor API client instance
    
    Raises:
        ValueError: If required configuration is missing
    """
    harbor_url = ocean.integration_config.get("harbor_url")
    username = ocean.integration_config.get("harbor_username")
    password = ocean.integration_config.get("harbor_password")
    verify_ssl = ocean.integration_config.get("verify_ssl", True)

    if not harbor_url:
        raise ValueError("harbor_url is required in integration config")
    if not username:
        raise ValueError("harbor_username is required in integration config")
    if not password:
        raise ValueError("harbor_password is required in integration config")

    return HarborClient(
        harbor_url=str(harbor_url),
        username=str(username),
        password=str(password),
        verify_ssl=bool(verify_ssl),
    )
