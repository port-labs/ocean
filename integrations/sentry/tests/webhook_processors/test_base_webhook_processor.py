import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Generator
import hashlib
import hmac
import json
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
        """When an original request is present without a signature, reject the event."""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.body = AsyncMock(return_value=b"{}")

        event = WebhookEvent(
            trace_id="t1", payload={}, headers={}, original_request=mock_request
        )

        proc = DummyProcessor(event)
        result = await proc.should_process_event(event)
        assert result is False

    async def test_should_process_event_without_original_request(self) -> None:
        """Reject events without original_request."""
        event = WebhookEvent(
            trace_id="t5",
            payload={},
            headers={"sentry-hook-signature": "test-signature"},
        )

        proc = DummyProcessor(event)
        result = await proc.should_process_event(event)
        assert result is False

    async def test_validate_payload_valid(self) -> None:
        """Accept valid custom integration payloads."""
        proc = DummyProcessor(
            WebhookEvent(
                trace_id="t7",
                payload={},
                headers={
                    "sentry-hook-signature": "test-signature",
                    "sentry-hook-resource": "issue",
                },
            )
        )
        valid_payload = {
            "action": "created",
            "data": {"issue": {}},
            "installation": {"uuid": "test-uuid"},
        }
        assert await proc.validate_payload(valid_payload) is True

    @pytest.mark.asyncio
    async def test_authenticate_no_secret_accepts_without_signature(
        self, mock_ocean_no_secret: MagicMock
    ) -> None:
        proc = DummyProcessor(WebhookEvent(trace_id="t-auth-1", payload={}, headers={}))
        payload: EventPayload = {"action": "created", "data": {"issue": {"id": "1"}}}
        assert await proc.authenticate(payload, {}) is True

    @pytest.mark.asyncio
    async def test_authenticate_with_secret_valid_signature(self) -> None:
        secret = "test-secret"
        payload: EventPayload = {"action": "created", "data": {"issue": {"id": "1"}}}
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        expected_sig = hmac.new(
            secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()

        with patch("webhook_processors.base_webhook_processor.ocean") as mock_ocean:
            mock_config = MagicMock()
            mock_config.get.return_value = secret
            mock_ocean.integration_config = mock_config

            proc = DummyProcessor(
                WebhookEvent(trace_id="t-auth-2", payload=payload, headers={})
            )
            assert (
                await proc.authenticate(
                    payload, {"sentry-hook-signature": expected_sig}
                )
                is True
            )

    @pytest.mark.parametrize(
        "headers",
        [
            {},
            {"sentry-hook-signature": "not-the-real-digest"},
        ],
    )
    @pytest.mark.asyncio
    async def test_authenticate_with_secret_rejects_missing_or_invalid_signature(
        self, headers: dict[str, str]
    ) -> None:
        secret = "test-secret"
        payload: EventPayload = {"action": "created", "data": {"issue": {"id": "1"}}}

        with patch("webhook_processors.base_webhook_processor.ocean") as mock_ocean:
            mock_config = MagicMock()
            mock_config.get.return_value = secret
            mock_ocean.integration_config = mock_config

            proc = DummyProcessor(
                WebhookEvent(trace_id="t-auth-3", payload=payload, headers=headers)
            )
            assert await proc.authenticate(payload, headers) is False
