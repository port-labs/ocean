from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_ocean_context() -> Generator[None, None, None]:
    mock_ocean = MagicMock()
    mock_ocean.app.is_saas.return_value = False
    mock_ocean.config.client_timeout = 60
    with patch("port_ocean.helpers.async_client.ocean", mock_ocean, create=True):
        yield
