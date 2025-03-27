import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from webhook_processors.monitor_webhook_processor import MonitorWebhookProcessor
from integration import ObjectKind
from typing import Any


@pytest.fixture
def mock_event() -> WebhookEvent:
    return WebhookEvent(trace_id="test", payload={}, headers={})


@pytest.fixture
def processor(mock_event: WebhookEvent) -> MonitorWebhookProcessor:
    return MonitorWebhookProcessor(mock_event)


@pytest.fixture
def resource_config() -> Any:
    return {"kind": ObjectKind.MONITOR}


@pytest.mark.asyncio
async def test_should_process_event(
    processor: MonitorWebhookProcessor, mock_event: WebhookEvent
) -> None:
    assert await processor.should_process_event(mock_event) is True


@pytest.mark.asyncio
async def test_get_matching_kinds(
    processor: MonitorWebhookProcessor, mock_event: WebhookEvent
) -> None:
    kinds = await processor.get_matching_kinds(mock_event)
    assert kinds == [ObjectKind.MONITOR]


@pytest.mark.asyncio
async def test_authenticate(processor: MonitorWebhookProcessor) -> None:
    assert await processor.authenticate({}, {}) is True


@pytest.mark.asyncio
async def test_validate_payload(processor: MonitorWebhookProcessor) -> None:
    assert (
        await processor.validate_payload({"event_type": "alert", "alert_id": "123"})
        is True
    )

    assert await processor.validate_payload({"alert_id": "123"}) is False

    assert await processor.validate_payload({"event_type": "alert"}) is False


@pytest.mark.asyncio
async def test_handle_event_with_monitor(
    processor: MonitorWebhookProcessor, resource_config: Any
) -> None:
    test_payload = {"event_type": "alert", "alert_id": "123"}
    mock_monitor = {"id": "123", "name": "Test Monitor"}

    with patch("webhook_processors.monitor_webhook_processor.init_client") as mock_init:
        mock_client = AsyncMock()
        mock_client.get_single_monitor.return_value = mock_monitor
        mock_init.return_value = mock_client

        result = await processor.handle_event(test_payload, resource_config)

        mock_client.get_single_monitor.assert_awaited_once_with("123")
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_monitor
        assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handle_event_without_monitor(
    processor: MonitorWebhookProcessor, resource_config: Any
) -> None:
    test_payload = {"event_type": "alert", "alert_id": "123"}

    with patch("webhook_processors.monitor_webhook_processor.init_client") as mock_init:
        mock_client = AsyncMock()
        mock_client.get_single_monitor.return_value = None
        mock_init.return_value = mock_client

        result = await processor.handle_event(test_payload, resource_config)

        mock_client.get_single_monitor.assert_awaited_once_with("123")
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
