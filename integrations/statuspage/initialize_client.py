from client import StatusPageClient
from port_ocean.context.ocean import ocean


def init_client() -> StatusPageClient:
    return StatusPageClient(
        statuspage_host=ocean.integration_config["statuspage_host"],
        statuspage_api_key=ocean.integration_config["statuspage_api_key"],
        statuspage_ids=ocean.integration_config.get("statuspage_ids"),
    )
