"""Shared fixtures for webhook processor tests."""

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    """Create a mock webhook event for testing."""
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    # Mock the original request for signature verification tests
    mock_request = MagicMock()
    mock_request.body = AsyncMock(return_value=b'{"test": "data"}')
    event._original_request = mock_request
    return event
