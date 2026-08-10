from unittest.mock import MagicMock, patch

import httpx
import pytest

from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.ip_blocker import IPBlockerTransport
from port_ocean.helpers.retry import RetryTransport


@pytest.mark.parametrize(
    ("disable_ip_outbound_blocker", "expected_outer_transport"),
    [
        (False, IPBlockerTransport),
        (True, RetryTransport),
    ],
)
def test_init_transport_wraps_with_ip_blocker_based_on_config(
    disable_ip_outbound_blocker: bool,
    expected_outer_transport: type[httpx.AsyncBaseTransport],
) -> None:
    mock_config = MagicMock()
    mock_config.disable_ip_outbound_blocker = disable_ip_outbound_blocker
    mock_config.ssl.third_party = MagicMock(verify=True)

    with patch("port_ocean.helpers.async_client.ocean") as mock_ocean:
        mock_ocean.config = mock_config
        client = OceanAsyncClient()
        transport = client._transport

    assert isinstance(transport, expected_outer_transport)
