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


def _event(
    action: str,
    asset_id: str,
    asset_type: str = "monitor",
    evt_name: str = "Monitor",
) -> dict:
    return {
        "attributes": {
            "evt": {"name": evt_name},
            "action": action,
            "asset": {"type": asset_type, "id": asset_id},
        }
    }


def _restriction_policy_event(action: str, resource_id: str) -> dict:
    """Restriction policy event where the resource is a monitor."""
    return _event(action, f"monitor:{resource_id}", "restriction_policy", "Access Management")


@pytest.fixture
def processor() -> MonitorWebhookProcessor:
    return MonitorWebhookProcessor(WebhookEvent(trace_id="test", payload={}, headers={}))


@pytest.fixture
def resource_config() -> SimpleNamespace:
    return SimpleNamespace(selector=SimpleNamespace(include_restriction_policy=True))


@pytest.mark.asyncio
async def test_should_process_event_matches_monitor_type(
    processor: MonitorWebhookProcessor,
) -> None:
    assert await processor.should_process_event(
        WebhookEvent(trace_id="ok", payload=_event("modified", "m-1"), headers={})
    ) is True


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_asset_type(
    processor: MonitorWebhookProcessor,
) -> None:
    assert await processor.should_process_event(
        WebhookEvent(trace_id="no", payload=_event("modified", "u-1", "user"), headers={})
    ) is False


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_evt_name(
    processor: MonitorWebhookProcessor,
) -> None:
    assert await processor.should_process_event(
        WebhookEvent(
            trace_id="no",
            payload=_event("modified", "m-1", evt_name="Access Management"),
            headers={},
        )
    ) is False


@pytest.mark.asyncio
async def test_should_process_event_false_resolved_action(
    processor: MonitorWebhookProcessor,
) -> None:
    # "resolved" is not a catalog-relevant lifecycle change — we skip it
    assert await processor.should_process_event(
        WebhookEvent(trace_id="no", payload=_event("resolved", "m-1"), headers={})
    ) is False


@pytest.mark.asyncio
async def test_handle_single_event_delete_returns_deleted(
    processor: MonitorWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    result = await processor.handle_event(
        _event("deleted", "m-1"), resource_config
    )
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "m-1"}]


@pytest.mark.asyncio
async def test_handle_single_event_404_returns_deleted(
    processor: MonitorWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    req = httpx.Request("GET", "https://api.datadoghq.com/api/v1/monitor/m-1")
    not_found = httpx.HTTPStatusError(
        "not found", request=req, response=httpx.Response(404, request=req)
    )
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.monitor_webhook_processor.MonitorExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.side_effect = not_found
        cls.return_value = exporter

        result = await processor.handle_event(
            _event("modified", "m-1"), resource_config
        )

    exporter.get_resource.assert_awaited_once_with(
        GetMonitorOptions(resource_id="m-1", include_restriction_policy=True)
    )
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "m-1"}]


@pytest.mark.asyncio
async def test_should_process_event_restriction_policy_for_monitor(
    processor: MonitorWebhookProcessor,
) -> None:
    # restriction_policy with monitor resource → should process
    assert await processor.should_process_event(
        WebhookEvent(
            trace_id="ok",
            payload=_restriction_policy_event("modified", "m-99"),
            headers={},
        )
    ) is True


@pytest.mark.asyncio
async def test_should_process_event_restriction_policy_non_monitor_skipped(
    processor: MonitorWebhookProcessor,
) -> None:
    # restriction_policy for a dashboard — should NOT process
    policy_event = _event("modified", "dashboard:d-1", "restriction_policy", "Access Management")
    assert await processor.should_process_event(
        WebhookEvent(trace_id="no", payload=policy_event, headers={})
    ) is False


@pytest.mark.asyncio
async def test_handle_single_event_restriction_policy_refetches_monitor(
    processor: MonitorWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.monitor_webhook_processor.MonitorExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.return_value = {"id": "m-99"}
        cls.return_value = exporter

        result = await processor.handle_event(
            _restriction_policy_event("modified", "m-99"), resource_config
        )

    # ID extracted from "monitor:m-99"
    exporter.get_resource.assert_awaited_once_with(
        GetMonitorOptions(resource_id="m-99", include_restriction_policy=True)
    )
    assert result.updated_raw_results == [{"id": "m-99"}]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_single_event_restriction_policy_deleted_refetches_monitor(
    processor: MonitorWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    """Deleting the restriction policy means the monitor still exists; refetch it."""
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.monitor_webhook_processor.MonitorExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.return_value = {"id": "m-99"}
        cls.return_value = exporter

        result = await processor.handle_event(
            _restriction_policy_event("deleted", "m-99"), resource_config
        )

    assert result.updated_raw_results == [{"id": "m-99"}]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_get_matching_kinds(processor: MonitorWebhookProcessor) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.MONITOR]
