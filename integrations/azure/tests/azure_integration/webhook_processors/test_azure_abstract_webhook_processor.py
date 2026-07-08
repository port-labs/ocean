from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

from azure_integration.webhook_processors._azure_abstract_webhook_processor import (
    AzureResourceEvent,
    AzureAbstractWebhookProcessor,
)


SUBSCRIPTION_ID = "test-subscription-id"
RESOURCE_URI = "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage"
RESOURCE_TYPE = "Microsoft.Storage/storageAccounts"


class ConcreteAzureWebhookProcessor(AzureAbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def handle_event(self, payload: EventPayload, resource_config: Any) -> Any:
        return None


@pytest.fixture
def cloud_event_payload() -> EventPayload:
    return {
        "specversion": "1.0",
        "id": "test-event-id",
        "source": "/subscriptions/test-subscription-id",
        "type": "Microsoft.Resources.ResourceWriteSuccess",
        "datacontenttype": "application/json",
        "time": "2026-07-03T00:00:00Z",
        "data": {
            "subscriptionId": SUBSCRIPTION_ID,
            "resourceUri": RESOURCE_URI,
            "operationName": "Microsoft.Storage/storageAccounts/write",
            "resourceProvider": "Microsoft.Storage",
        },
    }


@pytest.fixture
def mock_webhook_event(cloud_event_payload: EventPayload) -> WebhookEvent:
    return WebhookEvent(trace_id="trace-id", headers={}, payload=cloud_event_payload)


@pytest.fixture
def processor(mock_webhook_event: WebhookEvent) -> ConcreteAzureWebhookProcessor:
    return ConcreteAzureWebhookProcessor(event=mock_webhook_event)


def _mock_resource_type() -> Any:
    return patch(
        "azure_integration.webhook_processors._azure_abstract_webhook_processor.resolve_resource_type_from_resource_uri",
        return_value=RESOURCE_TYPE,
    )


class TestParseResourceEvent:
    def test_returns_parsed_resource_event(
        self,
        processor: ConcreteAzureWebhookProcessor,
        cloud_event_payload: EventPayload,
    ) -> None:
        with _mock_resource_type():
            result = processor._parse_resource_event(cloud_event_payload)

        assert result == AzureResourceEvent(
            id="test-event-id",
            type="Microsoft.Resources.ResourceWriteSuccess",
            subscription_id=SUBSCRIPTION_ID,
            resource_uri=RESOURCE_URI,
            operation_name="Microsoft.Storage/storageAccounts/write",
            resource_type=RESOURCE_TYPE,
            resource_provider="Microsoft.Storage",
        )

    def test_returns_none_for_invalid_payload(
        self,
        processor: ConcreteAzureWebhookProcessor,
    ) -> None:
        assert processor._parse_resource_event({"not": "a cloud event"}) is None

    def test_returns_none_when_resource_type_unresolvable(
        self,
        processor: ConcreteAzureWebhookProcessor,
        cloud_event_payload: EventPayload,
    ) -> None:
        with patch(
            "azure_integration.webhook_processors._azure_abstract_webhook_processor.resolve_resource_type_from_resource_uri",
            return_value=None,
        ):
            assert processor._parse_resource_event(cloud_event_payload) is None


class TestAuthenticate:
    async def test_always_returns_true(
        self,
        processor: ConcreteAzureWebhookProcessor,
        cloud_event_payload: EventPayload,
    ) -> None:
        assert await processor.authenticate(cloud_event_payload, {}) is True


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
                "azure_integration.webhook_processors._azure_abstract_webhook_processor.port_event",
                new=mock_event,
            ),
            patch(
                "azure_integration.webhook_processors._azure_abstract_webhook_processor.get_resource_configs_with_resource_kind",
                return_value=[mock_config],
            ),
        ):
            result = processor._get_matching_resource_configs(RESOURCE_TYPE)

        assert result == [mock_config]
