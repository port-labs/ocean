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

    # @pytest.mark.parametrize(
    #     "headers,secret,expected",
    #     [
    #         # Case 1: No signature header -> passes (API-registered webhooks)
    #         ({}, "some-secret", True),
    #         # Case 2: Signature present, but no secret configured -> fails
    #         ({"sentry-hook-signature": "s1"}, None, False),
    #         # Case 3: Signature present, secret present, match -> passes
    #         # hmac(sha256, "{}", "secret") = 769db...f66b
    #         (
    #             {
    #                 "sentry-hook-signature": "769db0058b88eb3427be559194246917f909565611488c594c3ac9a80392f66b"
    #             },
    #             "secret",
    #             True,
    #         ),
    #         # Case 4: Signature present, secret present, mismatch -> fails
    #         ({"sentry-hook-signature": "wrong-sig"}, "secret", False),
    #     ],
    # )
    # async def test_authenticate(
    #     self, headers: dict[str, str], secret: str | None, expected: bool
    # ) -> None:
    #     """Test authentication logic for various scenarios."""
    #     mock_request = Mock()
    #     mock_request.headers = headers
    #     mock_request.body = AsyncMock(return_value=b"{}")

    #     event = WebhookEvent(
    #         trace_id="t1",
    #         payload={},
    #         headers=headers,
    #         original_request=mock_request,
    #     )

    #     with patch("webhook_processors.base_webhook_processor.ocean") as mock_ocean:
    #         mock_config = MagicMock()
    #         mock_config.get.return_value = {"sentry_webhook_secret": secret}
    #         mock_ocean.integration_config = mock_config

    #         proc = DummyProcessor(event)
    #         assert await proc.authenticate({}, headers) is expected
