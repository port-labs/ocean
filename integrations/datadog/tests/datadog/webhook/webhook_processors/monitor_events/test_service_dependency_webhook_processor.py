import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.core.exporters.service_dependency_exporter import (
    GetServiceDependencyOptions,
)
from datadog.webhook.webhook_processors.monitor_events.service_dependency_webhook_processor import (
    ServiceDependencyWebhookProcessor,
)


@pytest.fixture
def mock_event() -> WebhookEvent:
    return WebhookEvent(trace_id="test", payload={}, headers={})


@pytest.fixture
def processor(mock_event: WebhookEvent) -> ServiceDependencyWebhookProcessor:
    return ServiceDependencyWebhookProcessor(mock_event)


@pytest.fixture
def resource_config() -> Any:
    mock_resource_config = MagicMock()
    mock_resource_config.kind = ObjectKind.SERVICE_DEPENDENCY
    mock_resource_config.selector.environment = "prod"
    mock_resource_config.selector.start_time = int(time.time()) - 60 * 60
    return mock_resource_config


@pytest.mark.asyncio
async def test_get_matching_kinds(
    processor: ServiceDependencyWebhookProcessor, mock_event: WebhookEvent
) -> None:
    kinds = await processor.get_matching_kinds(mock_event)
    assert kinds == [ObjectKind.SERVICE_DEPENDENCY]


@pytest.mark.asyncio
async def test_validate_payload(processor: ServiceDependencyWebhookProcessor) -> None:
    assert (
        await processor.validate_payload(
            {"event_type": "service_check", "tags": ["service:service-a", "env:prod"]}
        )
        is True
    )
    assert await processor.validate_payload({"event_type": "service_check"}) is False


@pytest.mark.asyncio
async def test_handle_event_with_service_dependency(
    processor: ServiceDependencyWebhookProcessor,
    resource_config: Any,
    mock_integration_config: dict[str, str],
) -> None:
    test_payload = {
        "event_type": "service_check",
        "tags": ["service:service-a", "env:prod"],
    }
    mock_service_dependency = {
        "service_id": "service-a",
        "service_name": "Test Service Dependency",
    }

    with (
        patch(
            "datadog.webhook.webhook_processors.monitor_events.service_dependency_webhook_processor.init_client"
        ) as mock_init,
        patch(
            "datadog.webhook.webhook_processors.monitor_events.service_dependency_webhook_processor.ServiceDependencyExporter"
        ) as mock_exporter_cls,
    ):
        mock_init.return_value = AsyncMock()
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = mock_service_dependency
        mock_exporter_cls.return_value = mock_exporter

        result = await processor.handle_event(test_payload, resource_config)

        mock_exporter.get_resource.assert_awaited_once_with(
            GetServiceDependencyOptions(
                service_id="service-a",
                env=resource_config.selector.environment,
                start_time=resource_config.selector.start_time,
            )
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_service_dependency
        assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handle_event_without_service_dependency(
    processor: ServiceDependencyWebhookProcessor,
    resource_config: Any,
) -> None:
    test_payload = {"event_type": "service_check", "tags": ["env:prod"]}

    with (
        patch(
            "datadog.webhook.webhook_processors.monitor_events.service_dependency_webhook_processor.init_client"
        ) as mock_init,
        patch(
            "datadog.webhook.webhook_processors.monitor_events.service_dependency_webhook_processor.ServiceDependencyExporter"
        ) as mock_exporter_cls,
    ):
        mock_init.return_value = AsyncMock()
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = None
        mock_exporter_cls.return_value = mock_exporter

        result = await processor.handle_event(test_payload, resource_config)
        mock_exporter.get_resource.assert_not_called()
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
