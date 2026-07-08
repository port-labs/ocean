from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import ResourceNotFoundError
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

from azure_integration.webhook_processors._azure_abstract_webhook_processor import (
    AzureResourceEvent,
)
from azure_integration.webhook_processors.resource_event_processor import (
    AzureResourceEventProcessor,
)


SUBSCRIPTION_ID = "test-subscription-id"
RESOURCE_URI = "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage"
RESOURCE_TYPE = "Microsoft.Storage/storageAccounts"
API_VERSION = "2026-07-02"


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
def processor(mock_webhook_event: WebhookEvent) -> AzureResourceEventProcessor:
    return AzureResourceEventProcessor(event=mock_webhook_event)


@pytest.fixture
def resource_config() -> MagicMock:
    config = MagicMock()
    config.kind = RESOURCE_TYPE
    config.selector.api_version = API_VERSION
    config.port.entity.mappings.blueprint = f'"{RESOURCE_TYPE}"'
    return config


@pytest.fixture
def parsed_resource_event() -> AzureResourceEvent:
    return AzureResourceEvent(
        id="test-event-id",
        type="Microsoft.Resources.ResourceWriteSuccess",
        subscription_id=SUBSCRIPTION_ID,
        resource_uri=RESOURCE_URI,
        operation_name="Microsoft.Storage/storageAccounts/write",
        resource_type=RESOURCE_TYPE,
        resource_provider="Microsoft.Storage",
    )


def _mock_resource_type() -> Any:
    return patch(
        "azure_integration.webhook_processors._azure_abstract_webhook_processor.resolve_resource_type_from_resource_uri",
        return_value=RESOURCE_TYPE,
    )


def _mock_matching_configs(configs: list[MagicMock] | None = None) -> Any:
    return patch(
        "azure_integration.webhook_processors._azure_abstract_webhook_processor.get_resource_configs_with_resource_kind",
        return_value=configs if configs is not None else [MagicMock()],
    )


def _mock_port_app_config() -> Any:
    mock_event = MagicMock()
    mock_event.port_app_config = MagicMock()
    return patch(
        "azure_integration.webhook_processors._azure_abstract_webhook_processor.port_event",
        new=mock_event,
    )


class TestShouldProcessEvent:
    async def test_returns_true_for_valid_event(
        self,
        processor: AzureResourceEventProcessor,
        mock_webhook_event: WebhookEvent,
    ) -> None:
        with _mock_resource_type(), _mock_port_app_config(), _mock_matching_configs():
            assert await processor.should_process_event(mock_webhook_event) is True

    async def test_returns_false_when_no_matching_config(
        self,
        processor: AzureResourceEventProcessor,
        mock_webhook_event: WebhookEvent,
    ) -> None:
        with (
            _mock_resource_type(),
            _mock_port_app_config(),
            _mock_matching_configs(configs=[]),
        ):
            assert await processor.should_process_event(mock_webhook_event) is False

    async def test_returns_false_for_unresolvable_resource(
        self,
        processor: AzureResourceEventProcessor,
        mock_webhook_event: WebhookEvent,
    ) -> None:
        with patch(
            "azure_integration.webhook_processors._azure_abstract_webhook_processor.resolve_resource_type_from_resource_uri",
            return_value=None,
        ):
            assert await processor.should_process_event(mock_webhook_event) is False

    async def test_sets_resource_event_on_success(
        self,
        processor: AzureResourceEventProcessor,
        mock_webhook_event: WebhookEvent,
    ) -> None:
        with _mock_resource_type(), _mock_port_app_config(), _mock_matching_configs():
            await processor.should_process_event(mock_webhook_event)

        assert processor._resource_event is not None
        assert processor._resource_event.resource_type == RESOURCE_TYPE


class TestGetMatchingKinds:
    @pytest.mark.parametrize(
        ("config_kind", "expected"),
        [
            pytest.param(RESOURCE_TYPE, [RESOURCE_TYPE], id="specific-kind"),
            pytest.param("cloudResource", ["cloudResource"], id="cloud-resource"),
        ],
    )
    async def test_returns_config_kind(
        self,
        processor: AzureResourceEventProcessor,
        mock_webhook_event: WebhookEvent,
        parsed_resource_event: AzureResourceEvent,
        config_kind: str,
        expected: list[str],
    ) -> None:
        processor._resource_event = parsed_resource_event
        mock_config = MagicMock()
        mock_config.kind = config_kind

        with _mock_port_app_config(), _mock_matching_configs(configs=[mock_config]):
            kinds = await processor.get_matching_kinds(mock_webhook_event)

        assert kinds == expected


class TestValidatePayload:
    async def test_returns_true_after_should_process_event_succeeds(
        self,
        processor: AzureResourceEventProcessor,
        cloud_event_payload: EventPayload,
        parsed_resource_event: AzureResourceEvent,
    ) -> None:
        processor._resource_event = parsed_resource_event
        assert await processor.validate_payload(cloud_event_payload) is True

    async def test_returns_false_before_should_process_event(
        self,
        processor: AzureResourceEventProcessor,
        cloud_event_payload: EventPayload,
    ) -> None:
        assert await processor.validate_payload(cloud_event_payload) is False


class TestHandleEvent:
    async def test_returns_updated_resource(
        self,
        processor: AzureResourceEventProcessor,
        cloud_event_payload: EventPayload,
        resource_config: MagicMock,
        mock_storage_account: dict[str, Any],
        parsed_resource_event: AzureResourceEvent,
    ) -> None:
        processor._resource_event = parsed_resource_event

        mock_resource = MagicMock()
        mock_resource.as_dict.return_value = mock_storage_account

        client = AsyncMock()
        client.resources.get_by_id = AsyncMock(return_value=mock_resource)

        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "azure_integration.webhook_processors.resource_event_processor.resource_client_context",
            return_value=context,
        ):
            result = await processor.handle_event(cloud_event_payload, resource_config)

        assert result.updated_raw_results == [mock_storage_account]
        assert result.deleted_raw_results == []

    async def test_returns_deleted_entity_when_resource_not_found(
        self,
        processor: AzureResourceEventProcessor,
        cloud_event_payload: EventPayload,
        resource_config: MagicMock,
        parsed_resource_event: AzureResourceEvent,
    ) -> None:
        processor._resource_event = parsed_resource_event

        client = AsyncMock()
        client.resources.get_by_id.side_effect = ResourceNotFoundError("not found")

        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "azure_integration.webhook_processors.resource_event_processor.resource_client_context",
            return_value=context,
        ):
            result = await processor.handle_event(cloud_event_payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [{"id": RESOURCE_URI}]
