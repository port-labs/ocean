from unittest.mock import MagicMock
import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    event._original_request = MagicMock()
    return event
