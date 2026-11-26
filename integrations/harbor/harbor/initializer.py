from port_ocean.context.ocean import ocean
from harbor.clients import HarborClient


def init_harbor_client() -> HarborClient:
    return HarborClient(
        harbor_host=ocean.integration_config["harbor_host"],
        harbor_username=ocean.integration_config["harbor_username"],
        harbor_password=ocean.integration_config["harbor_password"],
        verify_ssl=ocean.integration_config.get("verify_ssl", True),
    )
