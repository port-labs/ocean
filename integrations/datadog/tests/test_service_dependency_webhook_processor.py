import time
from typing import Any
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from webhook_processors.service_dependency_webhook_processor import (
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
            {"event_type": "service_check", "service_id": "123"}
        )
        is True
    )

    assert await processor.validate_payload({"service_id": "123"}) is False

    assert await processor.validate_payload({"event_type": "service_check"}) is False


@pytest.mark.asyncio
async def test_handle_event_with_service_dependency(
    processor: ServiceDependencyWebhookProcessor,
    resource_config: Any,
    mock_integration_config: dict[str, str],
) -> None:
    test_payload = {"event_type": "service_check", "service_id": "123"}
    mock_service_dependency = {
        "service_id": "123",
        "service_name": "Test Service Dependency",
    }

    with patch(
        "webhook_processors.service_dependency_webhook_processor.init_client"
    ) as mock_init:
        mock_client = AsyncMock()
        mock_client.get_single_service_dependency.return_value = mock_service_dependency
        mock_init.return_value = mock_client

        result = await processor.handle_event(test_payload, resource_config)

        mock_client.get_single_service_dependency.assert_awaited_once_with(
            service_id="123",
            env=resource_config.selector.environment,
            start_time=resource_config.selector.start_time,
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_service_dependency
        assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handle_event_without_service_dependency(
    processor: ServiceDependencyWebhookProcessor,
    resource_config: Any,
) -> None:
    test_payload = {"event_type": "service_check", "service_id": "123"}

    with patch(
        "webhook_processors.service_dependency_webhook_processor.init_client"
    ) as mock_init:
        mock_client = AsyncMock()
        mock_client.get_single_service_dependency.return_value = None
        mock_init.return_value = mock_client

        result = await processor.handle_event(test_payload, resource_config)
        mock_client.get_single_service_dependency.assert_awaited_once_with(
            service_id="123",
            env=resource_config.selector.environment,
            start_time=resource_config.selector.start_time,
        )
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
