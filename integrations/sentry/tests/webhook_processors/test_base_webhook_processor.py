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


def _make_request(body: bytes, headers: dict[str, str] | None = None) -> Mock:
    """Create a mock FastAPI Request with the given body and headers."""
    mock_request = Mock()
    mock_request.headers = headers or {}
    mock_request.body = AsyncMock(return_value=body)
    return mock_request


def _make_event(
    payload: EventPayload,
    headers: dict[str, str] | None = None,
    original_request: Mock | None = None,
) -> WebhookEvent:
    return WebhookEvent(
        trace_id="t1",
        payload=payload,
        headers=headers or {},
        original_request=original_request,
    )


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
    async def test_authenticate_always_returns_true(self) -> None:
        event = _make_event(VALID_PAYLOAD)
        proc = DummyProcessor(event)
        assert await proc.authenticate(VALID_PAYLOAD, {}) is True

    async def test_should_process_event_rejects_without_original_request(
        self, mock_ocean_no_secret: MagicMock
    ) -> None:
        event = _make_event(
            VALID_PAYLOAD,
            headers={"sentry-hook-resource": "issue"},
        )
        proc = DummyProcessor(event)
        assert await proc.should_process_event(event) is False

    async def test_should_process_event_rejects_non_issue_resource(
        self, mock_ocean_no_secret: MagicMock
    ) -> None:
        request = _make_request(b"{}")
        event = _make_event(
            VALID_PAYLOAD,
            headers={"sentry-hook-resource": "error"},
            original_request=request,
        )
        proc = DummyProcessor(event)
        assert await proc.should_process_event(event) is False

    async def test_should_process_event_rejects_unknown_action(
        self, mock_ocean_no_secret: MagicMock
    ) -> None:
        request = _make_request(b"{}")
        event = _make_event(
            {"action": "unknown_action"},
            headers={"sentry-hook-resource": "issue"},
            original_request=request,
        )
        proc = DummyProcessor(event)
        assert await proc.should_process_event(event) is False

    # -- Signature verification (via should_process_event) --

    async def test_no_secret_no_signature_accepts(
        self, mock_ocean_no_secret: MagicMock
    ) -> None:
        """Neither secret nor signature configured — accept."""
        request = _make_request(b"{}")
        event = _make_event(
            VALID_PAYLOAD,
            headers={"sentry-hook-resource": "issue"},
            original_request=request,
        )
        proc = DummyProcessor(event)
        assert await proc.should_process_event(event) is True

    async def test_no_secret_with_signature_accepts(
        self, mock_ocean_no_secret: MagicMock
    ) -> None:
        """No secret configured but signature present — accept with warning."""
        request = _make_request(
            b"{}",
            headers={"sentry-hook-signature": "some-signature"},
        )
        event = _make_event(
            VALID_PAYLOAD,
            headers={"sentry-hook-resource": "issue"},
            original_request=request,
        )
        proc = DummyProcessor(event)
        assert await proc.should_process_event(event) is True

    async def test_secret_without_signature_rejects(
        self, mock_ocean_with_secret: MagicMock
    ) -> None:
        """XOR mismatch: secret configured but no signature in request."""
        request = _make_request(b"{}")
        event = _make_event(
            VALID_PAYLOAD,
            headers={"sentry-hook-resource": "issue"},
            original_request=request,
        )
        proc = DummyProcessor(event)
        assert await proc.should_process_event(event) is False

    async def test_valid_signature_accepts(
        self, mock_ocean_with_secret: MagicMock
    ) -> None:
        """Both secret and valid signature — accept."""
        secret = "test-secret"
        body = json.dumps(
            VALID_PAYLOAD, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        valid_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

        request = _make_request(
            body,
            headers={"sentry-hook-signature": valid_sig},
        )
        event = _make_event(
            VALID_PAYLOAD,
            headers={"sentry-hook-resource": "issue"},
            original_request=request,
        )
        proc = DummyProcessor(event)
        assert await proc.should_process_event(event) is True

    async def test_invalid_signature_rejects(
        self, mock_ocean_with_secret: MagicMock
    ) -> None:
        """Both secret and signature present but signature is wrong — reject."""
        body = json.dumps(
            VALID_PAYLOAD, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

        request = _make_request(
            body,
            headers={"sentry-hook-signature": "not-the-real-digest"},
        )
        event = _make_event(
            VALID_PAYLOAD,
            headers={"sentry-hook-resource": "issue"},
            original_request=request,
        )
        proc = DummyProcessor(event)
        assert await proc.should_process_event(event) is False

    async def test_validate_payload_valid(self) -> None:
        """Accept valid custom integration payloads."""
        proc = DummyProcessor(
            _make_event(
                VALID_PAYLOAD,
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
