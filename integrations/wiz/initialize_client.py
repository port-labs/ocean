from wiz.client import WizClient
from port_ocean.context.ocean import ocean


def init_client() -> WizClient:
    return WizClient(
        ocean.integration_config["wiz_api_url"],
        ocean.integration_config["wiz_client_id"],
        ocean.integration_config["wiz_client_secret"],
        ocean.integration_config["wiz_token_url"],
    )
