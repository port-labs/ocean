from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

from azure_integration.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)

RESOURCE_TYPE = "Microsoft.Storage/storageAccounts"


class ConcreteAzureWebhookProcessor(BaseWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def handle_event(self, payload: EventPayload, resource_config: Any) -> Any:
        pass


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(trace_id="trace-id", headers={}, payload={})


@pytest.fixture
def processor(mock_webhook_event: WebhookEvent) -> ConcreteAzureWebhookProcessor:
    return ConcreteAzureWebhookProcessor(event=mock_webhook_event)


class TestAuthenticate:
    async def test_always_returns_true(
        self,
        processor: ConcreteAzureWebhookProcessor,
    ) -> None:
        assert await processor.authenticate({}, {}) is True


class TestGetMatchingResourceConfigs:
    def test_returns_matching_configs(
        self,
        processor: ConcreteAzureWebhookProcessor,
    ) -> None:
        mock_config = MagicMock()
        mock_event = MagicMock()
        mock_event.port_app_config = MagicMock()

        with (
            patch(
                "azure_integration.webhook.webhook_processors.base_webhook_processor.port_event",
                new=mock_event,
            ),
            patch(
                "azure_integration.webhook.webhook_processors.base_webhook_processor.get_resource_configs_with_resource_kind",
                return_value=[mock_config],
            ),
        ):
            result = processor._get_matching_resource_configs(RESOURCE_TYPE)

        assert result == [mock_config]
