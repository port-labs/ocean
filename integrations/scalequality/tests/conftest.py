from unittest.mock import MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture
def mock_ocean_context() -> None:
    """Initialize a minimal Ocean context so the client can be constructed in tests."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "scale_quality_api_url": "https://app.scalequality.io/v1",
            "scale_quality_api_key": "sq_live_test",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass
