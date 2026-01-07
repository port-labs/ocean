from typing import Optional

from loguru import logger

from harbor.client import HarborClient
from port_ocean.context.ocean import ocean

# Module-level singleton client instance
_harbor_client: Optional[HarborClient] = None


def _create_harbor_client() -> HarborClient:
    """
    Create a new Harbor client instance with configuration from ocean.
    
    This is an internal function that creates a new client instance.
    Use get_harbor_client() to get the singleton instance.
    
    Returns:
        HarborClient: Configured Harbor API client
    
    Raises:
        ValueError: If required configuration (base_url, username, password) is missing
    """
    base_url = ocean.integration_config.get("base_url")
    verify_ssl = ocean.integration_config.get("verify_ssl", False)
    api_version = ocean.integration_config.get("api_version", "v2.0")
    
    # Basic Auth is required - username and password must be provided
    username = ocean.integration_config.get("username")
    password = ocean.integration_config.get("password")
    
    if not username:
        raise ValueError(
            "Username is required for Harbor API authentication. "
            "Please set the 'username' configuration in your integration config."
        )
    
    if not password:
        raise ValueError(
            "Password is required for Harbor API authentication. "
            "Please set the 'password' configuration in your integration config."
        )
    
    logger.info(f"Harbor client configured with Basic Auth - username: {username}, base_url: {base_url}, api_version: {api_version}")
    
    return HarborClient(
        base_url=base_url,
        verify_ssl=verify_ssl,
        username=username,
        password=password,
        api_version=api_version,
    )


def get_harbor_client() -> HarborClient:
    """
    Get or create the singleton Harbor client instance.
    
    This function implements a singleton pattern to ensure only one
    HarborClient instance exists per integration instance. The client
    is created on first access and reused for subsequent calls.
    
    This prevents:
    - Race conditions from concurrent handler execution
    - Unnecessary object creation overhead
    - Configuration conflicts from multiple client instances
    
    Returns:
        HarborClient: The singleton Harbor API client instance
    """
    global _harbor_client
    
    if _harbor_client is None:
        _harbor_client = _create_harbor_client()
    
    return _harbor_client


def reset_harbor_client() -> None:
    """
    Reset the singleton client instance.
    
    This is primarily useful for testing or when configuration changes
    require a new client instance. The next call to get_harbor_client()
    will create a new client with the updated configuration.
    """
    global _harbor_client
    _harbor_client = None


# Backward compatibility alias
create_harbor_client = get_harbor_client

