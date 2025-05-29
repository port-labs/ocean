import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
