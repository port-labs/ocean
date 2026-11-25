from typing import Any

from port_ocean.context.ocean import ocean

from clients.devin_client import DevinClient

_devin_client: DevinClient | None = None


def create_devin_client() -> DevinClient:
    global _devin_client
    if _devin_client is not None:
        return _devin_client

    integration_config: dict[str, Any] = ocean.integration_config
    _devin_client = DevinClient(
        api_host=integration_config["devin_api_host"],
        api_key=integration_config["devin_api_key"],
        org_id=integration_config["devin_org_id"],
    )
    return _devin_client
