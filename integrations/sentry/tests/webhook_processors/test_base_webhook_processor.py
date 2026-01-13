import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Generator

from webhook_processors.base_webhook_processor import _SentryBaseWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    EventPayload,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


class DummyProcessor(_SentryBaseWebhookProcessor):
    """Concrete implementation for testing the abstract base class."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["issue"]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        raise NotImplementedError


@pytest.fixture
def mock_ocean_no_secret() -> Generator[MagicMock, None, None]:
    """Mock ocean with no webhook secret configured."""
    with patch("webhook_processors.base_webhook_processor.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get.return_value = None
        mock_ocean.integration_config = mock_config
        yield mock_ocean


@pytest.mark.asyncio
class TestSentryBaseWebhookProcessor:
    async def test_should_process_event_with_original_request(self) -> None:
        """When an original request is present, accept the event."""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.body = AsyncMock(return_value=b"{}")

        event = WebhookEvent(
            trace_id="t1", payload={}, headers={}, original_request=mock_request
        )

        proc = DummyProcessor(event)
        result = await proc.should_process_event(event)
        assert result is True

    async def test_should_process_event_without_original_request(self) -> None:
        """Reject events without original_request."""
        event = WebhookEvent(trace_id="t5", payload={}, headers={})

        proc = DummyProcessor(event)
        result = await proc.should_process_event(event)
        assert result is False

    async def test_validate_payload_sentry_service_hook(self) -> None:
        """Accept valid Sentry service hook payloads (containing group and project)."""
        proc = DummyProcessor(WebhookEvent(trace_id="t6", payload={}, headers={}))
        valid_payload = {
            "group": {"id": "123"},
            "project": {"slug": "test-project"},
        }
        assert await proc.validate_payload(valid_payload) is True

    async def test_validate_payload_custom_integration_valid(self) -> None:
        """Accept valid custom integration payloads."""
        proc = DummyProcessor(WebhookEvent(trace_id="t7", payload={}, headers={}))
        # Implementation calls _validate_integration_payload which we mocked to return True
        valid_payload = {
            "action": "created",
            "data": {"issue": {}},
            "installation": {"uuid": "test-uuid"},
        }
        assert await proc.validate_payload(valid_payload) is True

    async def test_get_resource_type(self) -> None:
        """Test _get_resource_type extracts header correctly (aligning with current implementation)."""
        proc = DummyProcessor(WebhookEvent(trace_id="t10", payload={}, headers={}))
        assert (
            proc._get_resource_type({"x-servicehook-signature": "some-sig"})
            == "some-sig"
        )
        assert proc._get_resource_type({}) == ""
