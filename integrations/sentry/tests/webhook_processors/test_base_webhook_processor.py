import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any, Generator, Tuple
import hashlib
import hmac

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

    def _validate_payload(self, payload: EventPayload) -> bool:
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


@pytest.fixture
def mock_ocean_with_secret() -> Generator[Tuple[MagicMock, str], None, None]:
    """Mock ocean with a webhook secret configured."""
    secret = "test-secret-123"
    with patch("webhook_processors.base_webhook_processor.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get.return_value = secret
        mock_ocean.integration_config = mock_config
        yield mock_ocean, secret


@pytest.mark.asyncio
class TestSentryBaseWebhookProcessor:
    async def test_should_process_event_no_secret_accepts(
        self, mock_ocean_no_secret: MagicMock
    ) -> None:
        """When no secret is configured, accept all events."""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.body = AsyncMock(return_value=b"{}")

        event = WebhookEvent(
            trace_id="t1", payload={}, headers={}, original_request=mock_request
        )

        proc = DummyProcessor(event)
        result = await proc.should_process_event(event)
        assert result is True

    async def test_should_process_event_with_valid_signature(
        self, mock_ocean_with_secret: Tuple[MagicMock, str]
    ) -> None:
        """Accept events with valid HMAC signature."""
        _, secret = mock_ocean_with_secret
        body = b'{"action": "created", "data": {}, "installation": {}}'
        expected_signature = hmac.new(
            secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()

        mock_request = Mock()
        mock_request.headers = {"sentry-hook-signature": expected_signature}
        mock_request.body = AsyncMock(return_value=body)

        event = WebhookEvent(
            trace_id="t2",
            payload={},
            headers={"sentry-hook-signature": expected_signature},
            original_request=mock_request,
        )

        proc = DummyProcessor(event)
        result = await proc.should_process_event(event)
        assert result is True

    async def test_should_process_event_with_invalid_signature(
        self, mock_ocean_with_secret: Tuple[MagicMock, str]
    ) -> None:
        """Reject events with invalid HMAC signature."""
        body = b'{"action": "created", "data": {}, "installation": {}}'

        mock_request = Mock()
        mock_request.headers = {"sentry-hook-signature": "invalid-signature"}
        mock_request.body = AsyncMock(return_value=body)

        event = WebhookEvent(
            trace_id="t3",
            payload={},
            headers={"sentry-hook-signature": "invalid-signature"},
            original_request=mock_request,
        )

        proc = DummyProcessor(event)
        result = await proc.should_process_event(event)
        assert result is False

    async def test_should_process_event_missing_signature_header(
        self, mock_ocean_with_secret: Tuple[MagicMock, str]
    ) -> None:
        """Reject events missing signature header when secret is configured."""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.body = AsyncMock(return_value=b"{}")

        event = WebhookEvent(
            trace_id="t4",
            payload={},
            headers={},
            original_request=mock_request,
        )

        proc = DummyProcessor(event)
        result = await proc.should_process_event(event)
        assert result is False

    async def test_should_process_event_without_original_request(self) -> None:
        """Reject events without original_request."""
        event = WebhookEvent(trace_id="t5", payload={}, headers={})

        proc = DummyProcessor(event)
        result = await proc.should_process_event(event)
        assert result is False

    async def test_validate_payload_valid(self) -> None:
        """Accept valid Sentry webhook payloads."""
        proc = DummyProcessor(WebhookEvent(trace_id="t6", payload={}, headers={}))
        valid_payload = {
            "action": "created",
            "data": {"issue": {}},
            "installation": {"uuid": "test-uuid"},
        }
        assert await proc.validate_payload(valid_payload) is True

    async def test_validate_payload_missing_action(self) -> None:
        """Reject payloads missing action field."""
        proc = DummyProcessor(WebhookEvent(trace_id="t7", payload={}, headers={}))
        invalid_payload: dict[str, Any] = {"data": {}, "installation": {}}
        assert await proc.validate_payload(invalid_payload) is False

    async def test_validate_payload_missing_data(self) -> None:
        """Reject payloads missing data field."""
        proc = DummyProcessor(WebhookEvent(trace_id="t8", payload={}, headers={}))
        invalid_payload = {"action": "created", "installation": {}}
        assert await proc.validate_payload(invalid_payload) is False

    async def test_validate_payload_missing_installation(self) -> None:
        """Reject payloads missing installation field."""
        proc = DummyProcessor(WebhookEvent(trace_id="t9", payload={}, headers={}))
        invalid_payload = {"action": "created", "data": {}}
        assert await proc.validate_payload(invalid_payload) is False

    async def test_get_resource_type(self) -> None:
        """Test _get_resource_type extracts header correctly."""
        proc = DummyProcessor(WebhookEvent(trace_id="t10", payload={}, headers={}))
        assert proc._get_resource_type({"sentry-hook-resource": "issue"}) == "issue"
        assert proc._get_resource_type({}) == ""
