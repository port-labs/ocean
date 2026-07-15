from typing import Any

import pytest
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

from gcp_core.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)


class ConcreteGCPWebhookProcessor(BaseWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def handle_event(self, payload: EventPayload, resource_config: Any) -> Any:
        return None


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(trace_id="trace-id", headers={}, payload={})


@pytest.fixture
def processor(mock_webhook_event: WebhookEvent) -> ConcreteGCPWebhookProcessor:
    return ConcreteGCPWebhookProcessor(event=mock_webhook_event)


class TestAuthenticate:
    async def test_always_returns_true(
        self,
        processor: ConcreteGCPWebhookProcessor,
    ) -> None:
        assert await processor.authenticate({}, {}) is True
