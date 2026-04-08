import pytest
from unittest.mock import patch, MagicMock
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


VALID_PAYLOAD: EventPayload = {
    "action": "created",
    "data": {"issue": {"id": "1"}},
}


@pytest.fixture
def mock_ocean_no_secret() -> Generator[MagicMock, None, None]:
    """Mock ocean with no webhook secret configured."""
    with patch("webhook_processors.base_webhook_processor.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get.return_value = None
        mock_ocean.integration_config = mock_config
        yield mock_ocean


@pytest.fixture
def mock_ocean_with_secret() -> Generator[MagicMock, None, None]:
    """Mock ocean with webhook secret configured."""
    with patch("webhook_processors.base_webhook_processor.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get.return_value = "test-secret"
        mock_ocean.integration_config = mock_config
        yield mock_ocean


@pytest.mark.asyncio
class TestSentryBaseWebhookProcessor:
    # -- should_process_event --

    async def test_should_process_event_accepts_valid_event(self) -> None:
        event = WebhookEvent(
            trace_id="t1",
            payload=VALID_PAYLOAD,
            headers={
                "sentry-hook-signature": "test-signature",
                "sentry-hook-resource": "issue",
            },
        )
        proc = DummyProcessor(event)
        assert await proc.should_process_event(event) is True

    async def test_should_process_event_rejects_missing_signature(self) -> None:
        event = WebhookEvent(
            trace_id="t2",
            payload=VALID_PAYLOAD,
            headers={"sentry-hook-resource": "issue"},
        )
        proc = DummyProcessor(event)
        assert await proc.should_process_event(event) is False

    async def test_should_process_event_rejects_non_issue_resource(self) -> None:
        event = WebhookEvent(
            trace_id="t3",
            payload=VALID_PAYLOAD,
            headers={
                "sentry-hook-signature": "test-signature",
                "sentry-hook-resource": "error",
            },
        )
        proc = DummyProcessor(event)
        assert await proc.should_process_event(event) is False

    async def test_should_process_event_rejects_unknown_action(self) -> None:
        event = WebhookEvent(
            trace_id="t4",
            payload={"action": "unknown_action"},
            headers={
                "sentry-hook-signature": "test-signature",
                "sentry-hook-resource": "issue",
            },
        )
        proc = DummyProcessor(event)
        assert await proc.should_process_event(event) is False

    # -- authenticate --

    async def test_authenticate_no_secret_accepts(
        self, mock_ocean_no_secret: MagicMock
    ) -> None:
        """No secret configured — skip verification."""
        proc = DummyProcessor(WebhookEvent(trace_id="t-auth-1", payload={}, headers={}))
        assert await proc.authenticate(VALID_PAYLOAD, {}) is True

    async def test_authenticate_no_secret_accepts_with_signature(
        self, mock_ocean_no_secret: MagicMock
    ) -> None:
        """No secret configured — skip verification even if signature is present."""
        proc = DummyProcessor(WebhookEvent(trace_id="t-auth-2", payload={}, headers={}))
        assert (
            await proc.authenticate(
                VALID_PAYLOAD, {"sentry-hook-signature": "some-sig"}
            )
            is True
        )

    async def test_authenticate_with_secret_valid_signature(
        self, mock_ocean_with_secret: MagicMock
    ) -> None:
        """Secret configured and valid signature — accept."""
        secret = "test-secret"
        body = json.dumps(
            VALID_PAYLOAD, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        valid_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

        proc = DummyProcessor(
            WebhookEvent(trace_id="t-auth-3", payload=VALID_PAYLOAD, headers={})
        )
        assert (
            await proc.authenticate(VALID_PAYLOAD, {"sentry-hook-signature": valid_sig})
            is True
        )

    async def test_authenticate_with_secret_missing_signature(
        self, mock_ocean_with_secret: MagicMock
    ) -> None:
        """Secret configured but no signature — reject."""
        proc = DummyProcessor(
            WebhookEvent(trace_id="t-auth-4", payload=VALID_PAYLOAD, headers={})
        )
        assert await proc.authenticate(VALID_PAYLOAD, {}) is False

    async def test_authenticate_with_secret_invalid_signature(
        self, mock_ocean_with_secret: MagicMock
    ) -> None:
        """Secret configured and wrong signature — reject."""
        proc = DummyProcessor(
            WebhookEvent(trace_id="t-auth-5", payload=VALID_PAYLOAD, headers={})
        )
        assert (
            await proc.authenticate(
                VALID_PAYLOAD, {"sentry-hook-signature": "not-the-real-digest"}
            )
            is False
        )

    # -- validate_payload --

    async def test_validate_payload_valid(self) -> None:
        proc = DummyProcessor(
            WebhookEvent(
                trace_id="t-val-1",
                payload=VALID_PAYLOAD,
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
