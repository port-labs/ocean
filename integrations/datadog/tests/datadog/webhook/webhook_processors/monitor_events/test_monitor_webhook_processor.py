from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.core.exporters.monitor_exporter import GetMonitorOptions
from datadog.webhook.webhook_processors.monitor_events.monitor_webhook_processor import (
    MonitorWebhookProcessor,
)


@pytest.fixture
def mock_event() -> WebhookEvent:
    return WebhookEvent(trace_id="test", payload={}, headers={})


@pytest.fixture
def processor(mock_event: WebhookEvent) -> MonitorWebhookProcessor:
    return MonitorWebhookProcessor(mock_event)


@pytest.fixture
def resource_config() -> SimpleNamespace:
    return SimpleNamespace(selector=SimpleNamespace(include_restriction_policy=False))


@pytest.mark.asyncio
async def test_get_matching_kinds(
    processor: MonitorWebhookProcessor, mock_event: WebhookEvent
) -> None:
    kinds = await processor.get_matching_kinds(mock_event)
    assert kinds == [ObjectKind.MONITOR]


@pytest.mark.asyncio
async def test_should_process_event(processor: MonitorWebhookProcessor) -> None:
    def _event(payload: dict[str, Any]) -> WebhookEvent:
        return WebhookEvent(trace_id="t", payload=payload, headers={})

    assert (
        await processor.should_process_event(
            _event({"event_type": "alert", "alert_id": "123"})
        )
        is True
    )
    assert await processor.should_process_event(_event({"alert_id": "123"})) is False
    assert (
        await processor.should_process_event(_event({"event_type": "alert"})) is False
    )


@pytest.mark.asyncio
async def test_handle_event_with_monitor(
    processor: MonitorWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    test_payload = {"event_type": "alert", "alert_id": "123"}
    mock_monitor = {"id": "123", "name": "Test Monitor"}

    with (
        patch(
            "datadog.webhook.webhook_processors.monitor_events.monitor_webhook_processor.init_client"
        ) as mock_init,
        patch(
            "datadog.webhook.webhook_processors.monitor_events.monitor_webhook_processor.MonitorExporter"
        ) as mock_exporter_cls,
    ):
        mock_init.return_value = AsyncMock()
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = mock_monitor
        mock_exporter_cls.return_value = mock_exporter

        result = await processor.handle_event(test_payload, resource_config)  # type: ignore[arg-type]

        mock_exporter.get_resource.assert_awaited_once_with(
            GetMonitorOptions(resource_id="123", include_restriction_policy=False)
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_monitor
        assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handle_event_without_monitor(
    processor: MonitorWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    test_payload = {"event_type": "alert", "alert_id": "123"}

    with (
        patch(
            "datadog.webhook.webhook_processors.monitor_events.monitor_webhook_processor.init_client"
        ) as mock_init,
        patch(
            "datadog.webhook.webhook_processors.monitor_events.monitor_webhook_processor.MonitorExporter"
        ) as mock_exporter_cls,
    ):
        mock_init.return_value = AsyncMock()
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = None
        mock_exporter_cls.return_value = mock_exporter

        result = await processor.handle_event(test_payload, resource_config)  # type: ignore[arg-type]

        mock_exporter.get_resource.assert_awaited_once_with(
            GetMonitorOptions(resource_id="123", include_restriction_policy=False)
        )
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
