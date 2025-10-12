from port_ocean.context.ocean import ocean
from harbor.client.harbor_client import HarborClient

# ============================================================================
# Client Initialization
# ============================================================================

def init_harbor_client() -> HarborClient:
    """Initialize and return a configured Harbor client.

    Reads configuration from ocean.integration_config and creates a client
    instance with the necessary authentication and connection parameters.

    Returns:
        HarborClient: Configured Harbor API client instance
    """
    return HarborClient(
        harbor_url=ocean.integration_config.get("harbor_url"),
        username=ocean.integration_config.get("harbor_username"),
        password=ocean.integration_config.get("harbor_password"),
        verify_ssl=ocean.integration_config.get("verify_ssl", True),
    )
