from typing import Union

from port_ocean.clients.port.client import PortClient


def get_port_client_for_integration(
    client_id: str,
    client_secret: str,
    integration_identifier: str,
    integration_type: str,
    integration_version: str,
    base_url: Union[str, None],
) -> PortClient:
    return PortClient(
        base_url=base_url or "https://api.getport/io",
        client_id=client_id,
        client_secret=client_secret,
        integration_identifier=integration_identifier,
        integration_type=integration_type,
        integration_version=integration_version,
    )
