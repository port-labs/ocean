import pytest
from unittest.mock import Mock

from okta.webhook_processors.base_webhook_processor import OktaBaseWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    EventPayload,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


class DummyProcessor(OktaBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["okta-user", "okta-group"]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        raise NotImplementedError


@pytest.mark.asyncio
class TestOktaBaseWebhookProcessor:
    async def test_should_process_event_no_secret_accepts(self) -> None:
        mock_request = Mock()
        mock_request.headers = {}

        event = WebhookEvent(
            trace_id="t1", payload={}, headers={}, original_request=mock_request
        )

        from port_ocean.context.ocean import ocean

        prev = ocean.integration_config.get("webhook_secret")
        ocean.app.config.integration.config["webhook_secret"] = ""
        try:
            proc = DummyProcessor(event)
            assert await proc.should_process_event(event) is True
        finally:
            ocean.app.config.integration.config["webhook_secret"] = prev

    async def test_should_process_event_with_secret_requires_match(self) -> None:
        from port_ocean.context.ocean import ocean

        ocean.app.config.integration.config["webhook_secret"] = "secret-123"

        # Wrong header
        mock_request_bad = Mock()
        mock_request_bad.headers = {"authorization": "not-it"}

        event_bad = WebhookEvent(
            trace_id="t2",
            payload={},
            headers={"authorization": "not-it"},
            original_request=mock_request_bad,
        )
        proc = DummyProcessor(event_bad)
        assert await proc.should_process_event(event_bad) is False

        # Correct header
        mock_request_good = Mock()
        mock_request_good.headers = {"authorization": "secret-123"}

        event_good = WebhookEvent(
            trace_id="t3",
            payload={},
            headers={"authorization": "secret-123"},
            original_request=mock_request_good,
        )
        proc = DummyProcessor(event_good)
        assert await proc.should_process_event(event_good) is True

    async def test_should_process_event_without_original_request_false(self) -> None:
        proc = DummyProcessor(WebhookEvent(trace_id="t4", payload={}, headers={}))
        assert await proc.should_process_event(proc.event) is False

    async def test_validate_payload(self) -> None:
        proc = DummyProcessor(WebhookEvent(trace_id="t5", payload={}, headers={}))
        assert await proc.validate_payload({"data": {"events": []}}) is True
        # Invalid payload should be rejected (no exception expected)
        assert await proc.validate_payload({}) is False
