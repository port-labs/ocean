from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.core.exporters.monitor_exporter import GetMonitorOptions
from datadog.webhook.webhook_processors.audit_trails.monitor_webhook_processor import (
    MonitorWebhookProcessor,
)


@pytest.fixture
def processor() -> MonitorWebhookProcessor:
    return MonitorWebhookProcessor(
        WebhookEvent(trace_id="test", payload={}, headers={})
    )


@pytest.fixture
def resource_config() -> SimpleNamespace:
    return SimpleNamespace(selector=SimpleNamespace(include_restriction_policy=True))


@pytest.mark.asyncio
async def test_should_process_event_matches_monitor_type_and_supported_action(
    processor: MonitorWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="ok",
        payload={"event": {"action": "resource.update", "asset": {"type": "monitor"}}},
        headers={},
    )
    wrong_type = WebhookEvent(
        trace_id="wrong-type",
        payload={"event": {"action": "resource.update", "asset": {"type": "user"}}},
        headers={},
    )

    assert await processor.should_process_event(event) is True
    assert await processor.should_process_event(wrong_type) is False


@pytest.mark.asyncio
async def test_handle_event_returns_deleted_result_for_delete_action(
    processor: MonitorWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    result = await processor.handle_event(
        {"event": {"action": "resource.delete", "asset": {"id": "m-1"}}},
        resource_config,
    )
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "m-1"}]


@pytest.mark.asyncio
async def test_handle_event_maps_404_to_deleted_result(
    processor: MonitorWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    error_response = httpx.Response(
        404,
        request=httpx.Request("GET", "https://api.datadoghq.com/api/v1/monitor/m-1"),
    )
    not_found = httpx.HTTPStatusError(
        "not found", request=error_response.request, response=error_response
    )

    with (
        patch(
            "datadog.webhook.webhook_processors.audit_trails.monitor_webhook_processor.init_client",
            return_value=AsyncMock(),
        ),
        patch(
            "datadog.webhook.webhook_processors.audit_trails.monitor_webhook_processor.MonitorExporter"
        ) as exporter_cls,
    ):
        exporter = AsyncMock()
        exporter.get_resource.side_effect = not_found
        exporter_cls.return_value = exporter

        result = await processor.handle_event(
            {"event": {"action": "resource.update", "asset": {"id": "m-1"}}},
            resource_config,
        )

    exporter.get_resource.assert_awaited_once_with(
        GetMonitorOptions(resource_id="m-1", include_restriction_policy=True)
    )
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "m-1"}]


@pytest.mark.asyncio
async def test_get_matching_kinds_and_validate_payload(
    processor: MonitorWebhookProcessor,
) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.MONITOR]
    assert await processor.validate_payload({"event": {"asset": {"id": "m-1"}}}) is True
    assert await processor.validate_payload({"event": {"asset": {}}}) is False
