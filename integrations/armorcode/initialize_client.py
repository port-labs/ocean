from clients.armorcode_client import ArmorcodeClient
from port_ocean.context.ocean import ocean

_global_client = None


def get_armorcode_client(base_url: str, api_key: str) -> ArmorcodeClient:
    global _global_client
    if _global_client is None:
        _global_client = ArmorcodeClient(base_url, api_key)
    return _global_client


def init_armorcode_client() -> ArmorcodeClient:
    return get_armorcode_client(
        base_url=ocean.integration_config["armorcode_api_base_url"],
        api_key=ocean.integration_config["armorcode_api_key"],
    )
