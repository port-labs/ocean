from client import FirehydrantClient
from port_ocean.context.ocean import ocean


def init_client() -> FirehydrantClient:
    return FirehydrantClient(
        ocean.integration_config["api_url"],
        ocean.integration_config["token"],
        ocean.integration_config.get("app_host", None),
    )
