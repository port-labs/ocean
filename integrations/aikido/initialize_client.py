from clients.aikido_client import AikidoClient
from port_ocean.context.ocean import ocean

_global_client = None


def get_aikido_client(
    base_url: str, client_id: str, client_secret: str
) -> AikidoClient:
    global _global_client
    if _global_client is None:
        _global_client = AikidoClient(base_url, client_id, client_secret)
    return _global_client


def init_aikido_client() -> AikidoClient:
    return get_aikido_client(
        base_url=ocean.integration_config["aikido_api_url"],
        client_id=ocean.integration_config["aikido_client_id"],
        client_secret=ocean.integration_config["aikido_client_secret"],
    )
