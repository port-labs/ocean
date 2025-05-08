from client import OctopusClient
from port_ocean.context.ocean import ocean


def init_octopus_client() -> OctopusClient:
    """Initialize and return a new OctopusClient instance"""
    return OctopusClient(
        ocean.integration_config["server_url"],
        ocean.integration_config["octopus_api_key"],
    )
