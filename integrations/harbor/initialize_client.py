from loguru import logger
from port_ocean.context.ocean import ocean

from client import HarborClient


def create_harbor_client() -> HarborClient:
    """
    Initialize and return Harbor client using integration configuration.

    Returns:
        Configured HarborClient instance
    """
    # Access integration config from ocean
    harbor_url = ocean.integration_config.get("harbor_url")
    username = ocean.integration_config.get("username")

    password = ocean.integration_config.get("password")

    if not harbor_url or not username or not password:
        raise ValueError(
            "Harbor configuration is incomplete. "
            "Please ensure harbor_url, username, and password are set."
        )

    logger.info(f"Initializing Harbor client for {harbor_url}")
    return HarborClient(
        harbor_url=harbor_url,
        username=username,
        password=password,
    )
