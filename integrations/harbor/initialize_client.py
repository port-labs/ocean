from typing import Optional

from harbor.client import HarborClient
from port_ocean.context.ocean import ocean


def create_harbor_client() -> HarborClient:
    """
    Create and return a Harbor client instance with configuration from ocean.
    
    This factory function centralizes client creation logic and handles
    authentication based on the configured auth type.
    
    Returns:
        HarborClient: Configured Harbor API client
    """
    base_url = ocean.integration_config.get("base_url")
    verify_ssl = ocean.integration_config.get("verify_ssl", False)
    auth_type = ocean.integration_config.get("auth_type", "none")
    
    # Determine authentication credentials based on auth type
    username: Optional[str] = None
    password: Optional[str] = None
    
    if auth_type == "basic":
        username = ocean.integration_config.get("username")
        password = ocean.integration_config.get("password")
    
    return HarborClient(
        base_url=base_url,
        verify_ssl=verify_ssl,
        username=username,
        password=password,
    )

