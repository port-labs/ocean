from typing import Union
from unittest.mock import MagicMock

from port_ocean.clients.port.client import PortClient
from port_ocean.config.settings import SslSettings
from port_ocean.context.ocean import initialize_port_ocean_context, ocean
from port_ocean.ocean import Ocean


def ensure_ocean_context_for_standalone_port_client() -> None:
    """Bootstrap a minimal Ocean context for helpers that construct PortClient directly.

    Standalone PortClient usage (smoke tests, get_port_client_for_integration) does not
    run through Ocean.__init__; SSL settings are read from ocean.config when the HTTP
    client is first used.
    """
    if ocean.initialized:
        return

    mock_ocean = MagicMock(spec=Ocean)
    mock_ocean.is_saas.return_value = False
    mock_ocean.config = MagicMock()
    mock_ocean.config.ssl = SslSettings()
    initialize_port_ocean_context(mock_ocean)


def get_port_client_for_integration(
    client_id: str,
    client_secret: str,
    integration_identifier: str,
    integration_type: str,
    integration_version: str,
    base_url: Union[str, None],
) -> PortClient:
    ensure_ocean_context_for_standalone_port_client()

    return PortClient(
        base_url=base_url or "https://api.getport/io",
        client_id=client_id,
        client_secret=client_secret,
        integration_identifier=integration_identifier,
        integration_type=integration_type,
        integration_version=integration_version,
        ingest_url="https://ingest.getport.io",
    )
