import base64
import json
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.context.event import EventContext

_CAESAR_OFFSET = 4

SAMPLE_ACTIVATION_PAYLOAD = {
    "email": "test@example.com",
    "userKey": "test-user-key",
    "wsEnvUrl": "https://saas.mend.io",
    "orgUuid": "test-org-uuid-1234",
}


def _make_activation_key(payload: dict[str, Any]) -> str:
    """Build a valid Mend activation key from a plain-dict payload."""
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    jwt_string = f"{header}.{body}."
    b64 = base64.b64encode(jwt_string.encode()).decode()
    reversed_b64 = b64[::-1]
    return "".join(chr(ord(c) + _CAESAR_OFFSET) for c in reversed_b64)


SAMPLE_ACTIVATION_KEY = _make_activation_key(SAMPLE_ACTIVATION_PAYLOAD)


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.is_saas.return_value = False
        mock_ocean_app.config.integration.config = {
            "mend_activation_key": SAMPLE_ACTIVATION_KEY,
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        # Stub cache_provider so @cache_iterator_result falls through to the
        # underlying fetch in tests (no real cache backend in unit tests).
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    mock_event = MagicMock(spec=EventContext)
    mock_event.event_type = "test_event"
    mock_event.trigger_type = "manual"
    mock_event.attributes = {}
    mock_event._deadline = 999999999.0
    mock_event._aborted = False

    with patch("port_ocean.context.event.event", mock_event):
        yield mock_event
