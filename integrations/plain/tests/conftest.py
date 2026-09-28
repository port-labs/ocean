"""Ocean context for unit tests.

Initialized at import time so ``main`` decorators keep the original handlers.
"""

from unittest.mock import MagicMock

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


def _passthrough(function: object, kind: str | None = None) -> object:
    return function


try:
    mock_ocean_app = MagicMock()
    mock_ocean_app.config.integration.config = {"api_token": "plainApiKey_test"}
    mock_ocean_app.config.client_timeout = 30
    mock_ocean_app.config.event_listener.should_resync = True
    mock_ocean_app.integration.on_resync.side_effect = _passthrough
    mock_ocean_app.integration.on_start.side_effect = _passthrough
    initialize_port_ocean_context(mock_ocean_app)
except PortOceanContextAlreadyInitializedError:
    pass
