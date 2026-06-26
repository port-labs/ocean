import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from checkmarx_one.webhook.events import CheckmarxEventType


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        payload={},
        headers={"x-cx-webhook-event": CheckmarxEventType.SCAN_COMPLETED},
    )
